#!/bin/bash
# Runs ON the RunPod pod. Env provided: R2_EP, R2_BUCKET, R2_AK, R2_SK, RUN_TAG
# Fetches pages archive + manifest from R2, embeds with 3 backbones,
# uploads results, then self-destructs the pod.
set -x
cd /workspace
S3="--aws-sigv4 aws:amz:auto:s3 --user ${R2_AK}:${R2_SK}"
BASE="${R2_EP}/${R2_BUCKET}/claude-repo"

pip install -q open_clip_torch pillow numpy
curl -s $S3 -o pages.tar "${BASE}/embed_in/${RUN_TAG}_pages.tar" || exit 1
curl -s $S3 -o manifest.csv "${BASE}/embed_in/${RUN_TAG}_manifest.csv" || exit 1
tar -xf pages.tar

python3 - <<'PYEOF'
import csv, numpy as np, torch, open_clip
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

rows = list(csv.reader(open("manifest.csv")))  # page_id, rel_image_path
device = "cuda"
BACKBONES = [
    ("clip_vitl14", "ViT-L-14", "openai"),
    ("siglip_b16", "ViT-B-16-SigLIP-384", "webli"),
    ("dinov2_vitb14", None, None),
]
for tag, arch, pretrain in BACKBONES:
    if arch:
        model, _, preprocess = open_clip.create_model_and_transforms(arch, pretrained=pretrain)
        model = model.to(device).eval()
        encode = lambda batch: model.encode_image(batch)
    else:
        model = torch.hub.load("facebookresearch/dinov2", "dinov2_vitb14").to(device).eval()
        from torchvision import transforms
        preprocess = transforms.Compose([
            transforms.Resize(256), transforms.CenterCrop(224), transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        encode = lambda batch: model(batch)
    feats, ids, batch, bids = [], [], [], []
    with torch.no_grad():
        for pid, path in rows:
            try:
                img = preprocess(Image.open(path).convert("RGB"))
            except Exception:
                continue
            batch.append(img); bids.append(pid)
            if len(batch) == 64:
                feats.append(encode(torch.stack(batch).to(device)).cpu().half().numpy())
                ids += bids; batch, bids = [], []
        if batch:
            feats.append(encode(torch.stack(batch).to(device)).cpu().half().numpy())
            ids += bids
    np.savez_compressed(f"{tag}.npz", emb=np.concatenate(feats), page_id=np.array(ids))
    print(tag, "done", len(ids), flush=True)
    del model
    torch.cuda.empty_cache()
PYEOF

for f in clip_vitl14 siglip_b16 dinov2_vitb14; do
  curl -s $S3 -X PUT --data-binary @${f}.npz "${BASE}/embed_out/${RUN_TAG}_${f}.npz"
done
curl -s $S3 -X PUT -d "done" "${BASE}/embed_out/${RUN_TAG}_DONE"
runpodctl remove pod "$RUNPOD_POD_ID"
