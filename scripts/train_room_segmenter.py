#!/usr/bin/env python3
"""G2: fine-tune SAM 2.1 Small's MASK DECODER on human-confirmed room outlines.

CODE ONLY. `--dry-run` runs offline on CPU with a tiny stand-in decoder and
never touches the network, sam2, or a GPU. A real run requires torch + sam2 in
the GPU container (data/training/TRAIN_RUNBOOK.md) and an eligible manifest from
scripts/build_training_manifest.py.

ARCHITECTURE (GEOMETRY_REBOOT_V1 G2)
------------------------------------
* Backbone: SAM 2.1 Hiera-Small. The IMAGE ENCODER IS FROZEN; we train only the
  prompt encoder + mask decoder head. This mirrors the sam2 training README
  pattern (facebookresearch/sam2 training/README.md), which fine-tunes the
  decoder while keeping the pretrained image encoder fixed — cheap, fits a
  single 24GB GPU, and appropriate for our small in-domain dataset.
* Prompt = the room-label POINT (positive), identical to the inference path in
  scripts/sam_smoke_runner.py (SAM2ImagePredictor.predict(point_coords=...)),
  so training and serving see the same prompt.
* Ground truth = human polygon rasterized to a mask (scripts/geometry_raster).
* Loss = BCE-with-logits + soft Dice on the predicted mask logits.
* Val = held-out PROJECT(s) from the manifest split ONLY (never random crops).
* Metrics, per project: mask IoU, boundary F1, area error % (predicted mask
  area vs human polygon area, both in px then ft^2 via px_per_foot).
* Fixed seeds, checkpointing, and a full config dump into the output dir.

24GB GPU SIZING (3090/4090): image side 1024, per-device batch 1, grad-accum 8
(effective batch 8), AdamW lr 1e-4 on decoder params only, bf16 autocast. These
defaults keep peak memory well under 24GB with the image encoder frozen (no
encoder activations retained for backward).

DIAGNOSTIC-WEAK GUARD
---------------------
A manifest with tier=diagnostic_weak (built from machine proposals) is REFUSED
for a real run unless --allow-diagnostic-weak is passed. Even then every output
(config, checkpoint meta, metrics) is stamped promotion_eligible=false: its
numbers may prove only that the harness runs, loss decreases, and checkpoints
save/restore — never promotion, demos, or architecture verdicts.

USAGE
-----
  # offline plumbing proof (no sam2/torch/GPU needed):
  python3 scripts/train_room_segmenter.py --dry-run

  # diagnostic_weak smoke (on the pod, machine-proposal manifest):
  python3 scripts/train_room_segmenter.py \
      --manifest data/training/manifest_diag_weak.json \
      --allow-diagnostic-weak --out out/g2_diag_weak --epochs 20

  # real run (on the pod, eligible human-truth manifest):
  python3 scripts/train_room_segmenter.py \
      --manifest data/training/manifest_v2.json --out out/g2_v1 --epochs 40
"""
import argparse
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from geometry_raster import (boundary_f1, mask_iou, polygon_to_mask,  # noqa: E402
                             shoelace_area)

# ---- soft import guards: none of these may be a hard failure at import time --
try:
    import numpy as np
except Exception:  # numpy is present here, but keep symmetry
    np = None

try:
    import torch
    import torch.nn.functional as F
    _HAVE_TORCH = True
except Exception:
    torch = None
    F = None
    _HAVE_TORCH = False

try:
    from sam2.build_sam import build_sam2  # noqa: F401
    from sam2.sam2_image_predictor import SAM2ImagePredictor  # noqa: F401
    _HAVE_SAM2 = True
except Exception:
    _HAVE_SAM2 = False


DEFAULTS = {
    "image_side": 1024,
    "batch_size": 1,
    "grad_accum": 8,
    "lr": 1e-4,
    "weight_decay": 0.01,
    "epochs": 40,
    "seed": 1337,
    "model_cfg": "configs/sam2.1/sam2.1_hiera_s.yaml",
    "checkpoint": "sam2.1_hiera_small.pt",
    "freeze_image_encoder": True,
    "amp_dtype": "bfloat16",
}


def set_seed(seed):
    random.seed(seed)
    if np is not None:
        np.random.seed(seed)
    if _HAVE_TORCH:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def load_manifest(path):
    with open(path) as f:
        return json.load(f)


def split_samples(manifest):
    train = [s for s in manifest["samples"] if s["split"] == "train"]
    val = [s for s in manifest["samples"] if s["split"] == "val"]
    return train, val


# ===========================================================================
# STAND-IN decoder for --dry-run (proves plumbing WITHOUT sam2/GPU).
# Backend-agnostic: uses torch if available, else a pure-numpy micro-model.
# Documented substitution: this is NOT SAM; it only exercises data load ->
# rasterize -> forward -> loss(decreasing) -> backward -> checkpoint save/restore.
# ===========================================================================
class NumpyStandInDecoder:
    """A 1-parameter logistic 'decoder': p = sigmoid(w*prompt_feat + b).

    Just enough to show a loss that decreases and a checkpoint round-trip with
    no torch. It predicts a constant fill probability per crop from a scalar
    prompt feature — a placeholder for the SAM mask decoder, nothing more.
    """

    def __init__(self, seed=0):
        rng = np.random.RandomState(seed)
        self.w = float(rng.randn() * 0.01)
        self.b = 0.0

    def state_dict(self):
        return {"w": self.w, "b": self.b}

    def load_state_dict(self, sd):
        self.w = sd["w"]
        self.b = sd["b"]

    def step(self, feats, targets, lr=0.5):
        # targets = per-sample fraction of positive pixels (in [0,1])
        loss = 0.0
        gw = gb = 0.0
        for x, t in zip(feats, targets):
            z = self.w * x + self.b
            p = 1.0 / (1.0 + np.exp(-z))
            loss += -(t * np.log(p + 1e-9) + (1 - t) * np.log(1 - p + 1e-9))
            gw += (p - t) * x
            gb += (p - t)
        n = max(1, len(feats))
        self.w -= lr * gw / n
        self.b -= lr * gb / n
        return loss / n


def _torch_standin():
    import torch.nn as nn

    class TorchStandInDecoder(nn.Module):
        def __init__(self):
            super().__init__()
            # tiny conv "decoder": 1x1 conv from a fake 4-ch embedding -> 1 logit
            self.head = nn.Conv2d(4, 1, kernel_size=1)

        def forward(self, emb):
            return self.head(emb)  # (B,1,H,W) logits

    return TorchStandInDecoder()


def dry_run(args):
    """Offline plumbing proof. No sam2, no GPU, no network. Exits 0 on success."""
    set_seed(args.seed)
    print("=== DRY RUN — stand-in decoder, CPU, no sam2/GPU/network ===")
    print(f"[dry] torch available: {_HAVE_TORCH}; sam2 available: {_HAVE_SAM2}")
    os.makedirs(args.out, exist_ok=True)

    # 1) DATA PATH PROOF: rasterize a real (or fake) polygon -> mask, prove the
    #    pos-pixel fraction is a sane target in [0,1].
    manifest = None
    if args.manifest and os.path.exists(args.manifest):
        manifest = load_manifest(args.manifest)
    samples = (manifest or {}).get("samples", [])
    if samples:
        s = samples[0]
        poly = s["polygon_px"]
        w, h = s["crop_wh"]
        mask = polygon_to_mask(poly, w, h)
        frac = float(mask.mean())
        print(f"[dry] rasterized sample {s['task_id']}: crop {w}x{h}, "
              f"pos-fraction={frac:.4f}, shoelace_px={shoelace_area(poly):.0f}")
        feats = [float(np.mean(s.get("prompt_point_px") or [0.5, 0.5])) / max(w, h)]
        targets = [frac]
    else:
        # synthesize one fake batch so --dry-run works with NO manifest at all
        print("[dry] no manifest samples; synthesizing one fake batch")
        poly = [[100, 100], [400, 100], [400, 500], [100, 500]]
        mask = polygon_to_mask(poly, 512, 640)
        feats = [0.5]
        targets = [float(mask.mean())]

    # 2) MODEL + LOSS-DECREASES + BACKWARD PROOF
    if _HAVE_TORCH:
        model = _torch_standin()
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        emb = torch.randn(1, 4, 16, 16)
        target = torch.full((1, 1, 16, 16), float(targets[0]))
        losses = []
        for _ in range(5):
            opt.zero_grad()
            logits = model(emb)
            loss = F.binary_cross_entropy_with_logits(logits, target)
            loss.backward()
            opt.step()
            losses.append(float(loss))
        backend = "torch"
        ckpt_obj = {k: v.detach().cpu().numpy().tolist()
                    for k, v in model.state_dict().items()}
    else:
        model = NumpyStandInDecoder(seed=args.seed)
        losses = [model.step(feats, targets) for _ in range(5)]
        backend = "numpy"
        ckpt_obj = model.state_dict()

    losses = [float(x) for x in losses]
    print(f"[dry] backend={backend}  loss curve: "
          f"{[round(x, 5) for x in losses]}")
    assert losses[-1] <= losses[0] + 1e-6, "loss did not decrease — plumbing bug"
    print("[dry] OK: loss decreased")

    # 3) CHECKPOINT SAVE/RESTORE PROOF
    ckpt_path = os.path.join(args.out, "standin_ckpt.json")
    with open(ckpt_path, "w") as f:
        json.dump(ckpt_obj, f)
    reloaded = json.load(open(ckpt_path))
    assert reloaded == ckpt_obj, "checkpoint round-trip mismatch"
    print(f"[dry] OK: checkpoint saved + restored ({ckpt_path})")

    dump_config(args, tier=(manifest or {}).get("tier", "n/a"),
                extra={"dry_run": True, "backend": backend,
                       "loss_curve": losses})
    print("[dry] DRY RUN PASSED — harness plumbing verified offline.")
    return 0


# ===========================================================================
# REAL run (executes only in the GPU container with torch + sam2).
# ===========================================================================
def dice_bce_loss(logits, target):
    bce = F.binary_cross_entropy_with_logits(logits, target)
    prob = torch.sigmoid(logits)
    num = 2 * (prob * target).sum() + 1.0
    den = prob.sum() + target.sum() + 1.0
    dice = 1 - num / den
    return bce + dice


def _load_crop_rgb(path):
    from PIL import Image
    return np.array(Image.open(path).convert("RGB"))


def build_gt_mask(sample):
    w, h = sample["crop_wh"]
    return polygon_to_mask(sample["polygon_px"], w, h)


def real_train(args):
    if not _HAVE_TORCH or not _HAVE_SAM2:
        raise SystemExit(
            "real run needs torch + sam2 in the GPU container. Missing: "
            + ("torch " if not _HAVE_TORCH else "")
            + ("sam2" if not _HAVE_SAM2 else "")
            + ". Use --dry-run offline, or run inside the pod (TRAIN_RUNBOOK.md).")

    manifest = load_manifest(args.manifest)
    tier = manifest.get("tier")
    if tier == "diagnostic_weak" and not args.allow_diagnostic_weak:
        raise SystemExit(
            "manifest tier=diagnostic_weak (machine proposals). REFUSED for a "
            "real run. Pass --allow-diagnostic-weak ONLY for the plumbing smoke; "
            "its metrics may never be cited for promotion/demo/architecture.")
    if tier != "human_truth" and not args.allow_diagnostic_weak:
        raise SystemExit(f"manifest tier={tier} not trainable; need human_truth "
                         "or explicit --allow-diagnostic-weak.")
    promotion_eligible = bool(manifest.get("eligible")) and tier == "human_truth"

    set_seed(args.seed)
    os.makedirs(args.out, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    train, val = split_samples(manifest)
    if not train:
        raise SystemExit("no train samples in manifest.")
    print(f"[train] tier={tier} promotion_eligible={promotion_eligible} "
          f"device={device} train={len(train)} val={len(val)}")

    # --- build SAM 2.1 Small, freeze image encoder, keep decoder trainable ---
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    sam = build_sam2(args.model_cfg, args.checkpoint, device=device)
    predictor = SAM2ImagePredictor(sam)
    model = predictor.model
    if args.freeze_image_encoder:
        for p in model.image_encoder.parameters():
            p.requires_grad_(False)
    train_params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(train_params, lr=args.lr, weight_decay=args.weight_decay)
    amp_dtype = getattr(torch, args.amp_dtype, torch.bfloat16)

    dump_config(args, tier=tier,
                extra={"promotion_eligible": promotion_eligible,
                       "n_train": len(train), "n_val": len(val),
                       "device": device,
                       "trainable_param_tensors": len(train_params)})

    best_iou = -1.0
    for epoch in range(args.epochs):
        model.train()
        random.shuffle(train)
        running = 0.0
        opt.zero_grad()
        for i, s in enumerate(train):
            rgb = _load_crop_rgb(os.path.join(ROOT, s["crop"]))
            gt = build_gt_mask(s)
            predictor.set_image(rgb)
            pt = np.array([s["prompt_point_px"]], dtype=np.float32)
            lbl = np.array([1], dtype=np.int64)
            with torch.autocast(device_type=device.split(":")[0], dtype=amp_dtype,
                                enabled=(device != "cpu")):
                # low-level predict with gradients on the decoder (image
                # embedding already cached by set_image; encoder is frozen).
                logits = _forward_mask_logits(predictor, model, pt, lbl, gt.shape)
                target = torch.from_numpy(gt).float().to(logits.device)[None, None]
                target = F.interpolate(target, size=logits.shape[-2:], mode="nearest")
                loss = dice_bce_loss(logits, target) / args.grad_accum
            loss.backward()
            running += float(loss) * args.grad_accum
            if (i + 1) % args.grad_accum == 0:
                opt.step()
                opt.zero_grad()
        opt.step()
        opt.zero_grad()
        metrics = evaluate(predictor, model, val) if val else {}
        mean_iou = metrics.get("overall", {}).get("mask_iou", float("nan"))
        print(f"[train] epoch {epoch} loss={running/max(1,len(train)):.4f} "
              f"val_iou={mean_iou}")
        save_checkpoint(args.out, "last", model, opt, epoch, metrics,
                        tier, promotion_eligible)
        if val and mean_iou == mean_iou and mean_iou > best_iou:
            best_iou = mean_iou
            save_checkpoint(args.out, "best", model, opt, epoch, metrics,
                            tier, promotion_eligible)
    print(f"[train] done. best_val_iou={best_iou}")
    return 0


def _forward_mask_logits(predictor, model, points_px, labels, gt_hw):
    """Run prompt-encoder + mask-decoder with grad, return single-mask logits.

    Kept in one place so the exact SAM2 decoder call is easy to pin to the
    installed sam2 version in the container. Uses the predictor's cached image
    embedding (image encoder frozen) and the point prompt only.
    """
    # NOTE: exact tensor plumbing depends on the pinned sam2 commit; the runbook
    # instructs pinning sam2 and running the --dry-run first. This mirrors
    # SAM2ImagePredictor.predict but keeps the graph for backward on the decoder.
    coords = torch.as_tensor(points_px, dtype=torch.float, device=model.device)[None]
    labs = torch.as_tensor(labels, dtype=torch.int, device=model.device)[None]
    coords = predictor._transforms.transform_coords(
        coords, normalize=True, orig_hw=predictor._orig_hw[-1])
    sparse, dense = model.sam_prompt_encoder(points=(coords, labs), boxes=None,
                                             masks=None)
    feats = predictor._features
    low_res, ious, _, _ = model.sam_mask_decoder(
        image_embeddings=feats["image_embed"][-1].unsqueeze(0),
        image_pe=model.sam_prompt_encoder.get_dense_pe(),
        sparse_prompt_embeddings=sparse,
        dense_prompt_embeddings=dense,
        multimask_output=False,
        repeat_image=False,
        high_res_features=[f[-1].unsqueeze(0) for f in feats["high_res_feats"]],
    )
    return low_res  # (1,1,h,w) logits


def evaluate(predictor, model, val):
    """Per-project mask IoU, boundary F1, area error %. No grad."""
    model.eval()
    per_project = {}
    ious, bfs, aerrs = [], [], []
    with torch.no_grad():
        for s in val:
            rgb = _load_crop_rgb(os.path.join(ROOT, s["crop"]))
            gt = build_gt_mask(s)
            predictor.set_image(rgb)
            masks, scores, _ = predictor.predict(
                point_coords=np.array([s["prompt_point_px"]], dtype=np.float32),
                point_labels=np.array([1], dtype=np.int64),
                multimask_output=False)
            pred = (masks[0] > 0).astype("uint8")
            iou = mask_iou(pred, gt)
            bf = boundary_f1(pred, gt)
            ppf = s.get("px_per_foot") or 1.0
            pred_sf = pred.sum() / (ppf * ppf)
            gt_sf = gt.sum() / (ppf * ppf)
            aerr = abs(pred_sf - gt_sf) / gt_sf * 100 if gt_sf else float("nan")
            ious.append(iou)
            bfs.append(bf)
            aerrs.append(aerr)
            per_project.setdefault(s["permit"], {"iou": [], "bf": [], "aerr": []})
            per_project[s["permit"]]["iou"].append(iou)
            per_project[s["permit"]]["bf"].append(bf)
            per_project[s["permit"]]["aerr"].append(aerr)

    def mean(x):
        x = [v for v in x if v == v]
        return sum(x) / len(x) if x else float("nan")

    out = {"overall": {"mask_iou": mean(ious), "boundary_f1": mean(bfs),
                       "area_error_pct": mean(aerrs), "n": len(val)},
           "per_project": {}}
    for p, d in per_project.items():
        out["per_project"][p] = {"mask_iou": mean(d["iou"]),
                                 "boundary_f1": mean(d["bf"]),
                                 "area_error_pct": mean(d["aerr"]),
                                 "n": len(d["iou"])}
    return out


def save_checkpoint(out_dir, tag, model, opt, epoch, metrics, tier, promotion_eligible):
    path = os.path.join(out_dir, f"ckpt_{tag}.pt")
    torch.save({
        "model": model.state_dict(),
        "optimizer": opt.state_dict(),
        "epoch": epoch,
        "metrics": metrics,
        "tier": tier,
        "promotion_eligible": promotion_eligible,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, path)
    with open(os.path.join(out_dir, f"metrics_{tag}.json"), "w") as f:
        json.dump({"epoch": epoch, "tier": tier,
                   "promotion_eligible": promotion_eligible,
                   "metrics": metrics}, f, indent=2)


def dump_config(args, tier, extra=None):
    cfg = {k: getattr(args, k) for k in vars(args)}
    cfg.update({
        "tier": tier,
        "have_torch": _HAVE_TORCH,
        "have_sam2": _HAVE_SAM2,
        "seed": args.seed,
        "defaults": DEFAULTS,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    if extra:
        cfg.update(extra)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "train_config.json"), "w") as f:
        json.dump(cfg, f, indent=2, default=str)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=None,
                    help="manifest_v<N>.json from build_training_manifest.py")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "g2_run"))
    ap.add_argument("--dry-run", action="store_true",
                    help="offline plumbing proof (no sam2/torch/GPU/network)")
    ap.add_argument("--allow-diagnostic-weak", action="store_true",
                    help="permit a real run on a diagnostic_weak manifest "
                         "(plumbing smoke only; metrics never citable)")
    ap.add_argument("--epochs", type=int, default=DEFAULTS["epochs"])
    ap.add_argument("--batch-size", type=int, default=DEFAULTS["batch_size"])
    ap.add_argument("--grad-accum", type=int, default=DEFAULTS["grad_accum"])
    ap.add_argument("--lr", type=float, default=DEFAULTS["lr"])
    ap.add_argument("--weight-decay", type=float, default=DEFAULTS["weight_decay"])
    ap.add_argument("--image-side", type=int, default=DEFAULTS["image_side"])
    ap.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    ap.add_argument("--model-cfg", default=DEFAULTS["model_cfg"])
    ap.add_argument("--checkpoint", default=DEFAULTS["checkpoint"])
    ap.add_argument("--freeze-image-encoder", action="store_true",
                    default=DEFAULTS["freeze_image_encoder"])
    ap.add_argument("--amp-dtype", default=DEFAULTS["amp_dtype"])
    args = ap.parse_args()

    if args.dry_run:
        return dry_run(args)
    if not args.manifest:
        raise SystemExit("real run needs --manifest (or use --dry-run).")
    return real_train(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
