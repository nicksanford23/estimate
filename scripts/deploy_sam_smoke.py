#!/usr/bin/env python3
"""Deploy + review orchestration for the SAM 2.1 room-segmentation smoke test on
permit 24-06748-RNVS (geometry reboot gate G1). CODE ONLY — no network call
happens unless you explicitly run `deploy`/`poll`/`terminate` (and `deploy` has
`--dry-run`). `plan` and `--dry-run` are pure local reads.

This is the "recorded before renting" side of the GPU experiment ladder
(GEOMETRY_REBOOT_V1.md §"GPU experiment ladder": no cloud GPU is rented until
the exact input bundle, container digest, checkpoint, command, output path, max
runtime, and budget cap are recorded).

Design lineage (both patterns are hard-won — see STATE.md "Failed Attempts"):
  * POD CREATION: embed_gpu.py's GraphQL podFindAndDeployOnDemand ladder
    (clouds SECURE->COMMUNITY, GPU-type fallback list) + the boot watchdog that
    terminates and hops if uptime stays 0 after 8 min (4090 community capacity
    is often dry). volumeInGb ALWAYS paired with volumeMountPath (a pod with
    volume but no mount path create-loops forever and never boots).
  * SHIP/START: deploy_pod.py's later lesson — GraphQL `dockerArgs` was found
    broken on this account, so we DO NOT bake a bootstrap into dockerArgs.
    Instead we boot the stock pinned pytorch image (sshd + injected PUBLIC_KEY),
    then TYPE commands over the account SSH proxy (ssh.runpod.io, suffix
    644115c8, key ~/.ssh/runpod_ed25519). The pod's old curl cannot sign R2
    SigV4, so ALL bytes move via presigned URLs: presigned GET for inputs
    (bundle tarball + runner script), presigned PUT for outputs (results tarball
    + DONE marker). No R2 creds ever land on the pod.
  * python3 on the pod is 3.8; we invoke python3.11 EXPLICITLY.
  * "pod created" != "pod working": the boot watchdog + the poll DONE-marker
    timeout both demand real progress, and every pod-creating path guarantees
    terminate-on-failure (try/finally) and prints the pod id FIRST so a human
    can always kill it manually.

Secrets: RUNPOD_API_KEY / R2_* are read from .env by NAME only and never
printed. The old key was exposed and MUST be rotated: a FRESH RUNPOD_API_KEY has
to be in .env before `deploy` (see DEPLOY_README.md).

Subcommands:
  plan       read bundle manifest, verify local sha256s, print + write the
             complete recorded experiment plan to deploy_plan.json. No network.
  deploy     upload bundle tarball to R2, create ONE GPU pod, ship + launch the
             remote run detached. --dry-run prints every action, no network.
  poll       watch the R2 DONE marker, enforce the wall-clock budget (terminate
             at max runtime regardless), download + extract results, verify.
  terminate  kill the pod (reads pod_state.json, or --podid).

Usage:
  python3 scripts/deploy_sam_smoke.py plan
  python3 scripts/deploy_sam_smoke.py deploy --dry-run
  python3 scripts/deploy_sam_smoke.py deploy
  python3 scripts/deploy_sam_smoke.py poll
  python3 scripts/deploy_sam_smoke.py terminate [--podid <id>]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMIT = "24-06748-RNVS"
SMOKE_DIR = os.path.join(ROOT, "data", "sam_smoke", PERMIT)
BUNDLE_DIR = os.path.join(SMOKE_DIR, "bundle")
PLAN_PATH = os.path.join(SMOKE_DIR, "deploy_plan.json")
POD_STATE_PATH = os.path.join(SMOKE_DIR, "pod_state.json")
RESULTS_GPU_DIR = os.path.join(SMOKE_DIR, "results_gpu")
RUNNER_LOCAL = os.path.join(ROOT, "scripts", "sam_smoke_runner.py")
VERIFY_LOCAL = os.path.join(ROOT, "scripts", "verify_sam_smoke_results.py")

# R2 key layout for this smoke test
R2_PREFIX_IN = "claude-repo/sam_smoke_in"
R2_PREFIX_OUT = "claude-repo/sam_smoke_out"
R2_BUNDLE_KEY = f"{R2_PREFIX_IN}/{PERMIT}_bundle.tar.gz"
R2_RUNNER_KEY = f"{R2_PREFIX_IN}/{PERMIT}_sam_smoke_runner.py"
R2_RESULTS_KEY = f"{R2_PREFIX_OUT}/{PERMIT}_results_gpu.tar.gz"
R2_DONE_KEY = f"{R2_PREFIX_OUT}/{PERMIT}_DONE"

# RunPod / SSH (from deploy_pod.py — this account)
GQL = "https://api.runpod.io/graphql"
SSH_ACCOUNT_SUFFIX = "644115c8"
SSH_KEY = os.path.expanduser("~/.ssh/runpod_ed25519")

# GPU creation ladder (embed_gpu.py). Cheap-first; 4090 community is often dry so
# we fall through. Rough on-demand $/hr for the dry-run cost math ONLY (the real
# gate uses the live costPerHr the API returns at create time).
GPU_LADDER = [
    "NVIDIA GeForce RTX 4090",
    "NVIDIA GeForce RTX 3090",
    "NVIDIA RTX A5000",
    "NVIDIA RTX A4500",
    "NVIDIA L4",
    "NVIDIA RTX 4000 Ada Generation",
]
GPU_PRICE_HINT_USD_HR = {
    "NVIDIA GeForce RTX 4090": 0.44,
    "NVIDIA GeForce RTX 3090": 0.22,
    "NVIDIA RTX A5000": 0.26,
    "NVIDIA RTX A4500": 0.21,
    "NVIDIA L4": 0.43,
    "NVIDIA RTX 4000 Ada Generation": 0.20,
}
CLOUDS = ("SECURE", "COMMUNITY")
POD_IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
REMOTE_HARD_TIMEOUT_S = 3000  # `timeout 3000s` around the runner (< 60 min cap)


# ---------------------------------------------------------------------------
# env / small utils
# ---------------------------------------------------------------------------
def load_env():
    """Read .env into a dict by KEY NAME. Values are never printed."""
    env = {}
    path = os.path.join(ROOT, ".env")
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest():
    with open(os.path.join(BUNDLE_DIR, "manifest.json")) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# RunPod GraphQL (create / poll uptime / terminate) — curl, key never echoed
# ---------------------------------------------------------------------------
def gql(query, env):
    r = subprocess.run(
        ["curl", "-s", "-m", "60", "-X", "POST", GQL,
         "-H", "content-type: application/json",
         "-H", f"Authorization: Bearer {env['RUNPOD_API_KEY']}",
         "-d", json.dumps({"query": query})],
        capture_output=True, timeout=90)
    try:
        return json.loads(r.stdout.decode())
    except json.JSONDecodeError:
        return {"_raw": r.stdout.decode()[:400]}


def pod_uptime(pod_id, env):
    r = gql('query { pod(input: {podId: "%s"}) { runtime { uptimeInSeconds } } }'
            % pod_id, env)
    rt = ((r.get("data") or {}).get("pod") or {}).get("runtime") or {}
    return rt.get("uptimeInSeconds") or 0


def terminate_pod(pod_id, env):
    gql('mutation { podTerminate(input: {podId: "%s"}) }' % pod_id, env)


# ---------------------------------------------------------------------------
# SSH-PTY (deploy_pod.py pattern): type a command list into the pod shell
# ---------------------------------------------------------------------------
def ssh_pty(pod_id, commands, timeout=900):
    user = f"{pod_id}-{SSH_ACCOUNT_SUFFIX}@ssh.runpod.io"
    payload = "".join(f"{c}\n" for c in commands) + "exit\n"
    p = subprocess.run(
        ["ssh", "-tt", "-o", "StrictHostKeyChecking=no",
         "-o", "UserKnownHostsFile=/dev/null", "-i", SSH_KEY, user],
        input=payload.encode(), capture_output=True, timeout=timeout)
    return p.stdout.decode(errors="ignore"), p.stderr.decode(errors="ignore")


# ---------------------------------------------------------------------------
# R2 (boto3) — upload input tarball, presign GET/PUT, check/download output
# ---------------------------------------------------------------------------
def r2_client(env):
    import boto3
    return boto3.client("s3", endpoint_url=env["R2_ENDPOINT"],
                        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
                        region_name="auto")


def presign(s3, env, key, method, expires=14400):
    op = "get_object" if method == "GET" else "put_object"
    return s3.generate_presigned_url(
        op, Params={"Bucket": env["R2_BUCKET"], "Key": key}, ExpiresIn=expires,
        HttpMethod=method)


# ---------------------------------------------------------------------------
# bundle tarball (deterministic member order)
# ---------------------------------------------------------------------------
def build_bundle_tarball(dest):
    files = sorted(os.listdir(BUNDLE_DIR))
    with tarfile.open(dest, "w:gz") as tar:
        for name in files:
            tar.add(os.path.join(BUNDLE_DIR, name), arcname=name)
    return files


# ---------------------------------------------------------------------------
# PLAN
# ---------------------------------------------------------------------------
def build_plan():
    man = load_manifest()
    bundle_files = {}
    mismatches = []
    for name, rec in man.get("bundle_files", {}).items():
        p = os.path.join(BUNDLE_DIR, name)
        if not os.path.exists(p):
            bundle_files[name] = {"error": "MISSING_LOCAL", "manifest": rec}
            mismatches.append(f"{name}: missing locally")
            continue
        local_sha = sha256_file(p)
        local_bytes = os.path.getsize(p)
        ok = local_sha == rec.get("sha256") and local_bytes == rec.get("bytes")
        if not ok:
            mismatches.append(f"{name}: sha/bytes mismatch vs manifest")
        bundle_files[name] = {
            "sha256": local_sha, "bytes": local_bytes,
            "manifest_sha256": rec.get("sha256"), "manifest_bytes": rec.get("bytes"),
            "matches_manifest": ok,
        }

    small_url = px_getcfg(man, "checkpoints", "small", "url")
    large_url = px_getcfg(man, "checkpoints", "large", "url")
    max_min = man.get("max_runtime_minutes", 60)
    budget = man.get("budget_cap_usd", 2)

    remote_cmds = remote_command_sequence(
        small_url, large_url,
        small_cfg="configs/sam2.1/sam2.1_hiera_s.yaml",
        large_cfg="configs/sam2.1/sam2.1_hiera_l.yaml",
        get_bundle="<presigned-GET bundle.tar.gz>",
        get_runner="<presigned-GET sam_smoke_runner.py>",
        put_results="<presigned-PUT results_gpu.tar.gz>",
        put_done="<presigned-PUT DONE>")

    plan = {
        "schema": "sam_smoke_deploy_plan_v1",
        "permit": PERMIT,
        "gate": man.get("gate", "G1"),
        "purpose": man.get("purpose"),
        "recorded_before_renting": True,
        "container_image": man.get("container_image", POD_IMAGE),
        "checkpoints": man.get("checkpoints"),
        "bundle_files": bundle_files,
        "bundle_sha_mismatches": mismatches,
        "r2": {
            "bucket_key_name": "R2_BUCKET (value in .env; not printed)",
            "input_bundle_key": R2_BUNDLE_KEY,
            "input_runner_key": R2_RUNNER_KEY,
            "output_results_key": R2_RESULTS_KEY,
            "output_done_marker_key": R2_DONE_KEY,
        },
        "remote_command_sequence": remote_cmds,
        "runner_command_small": man.get("runner_command"),
        "output_local_dir": os.path.relpath(RESULTS_GPU_DIR, ROOT),
        "max_runtime_minutes": max_min,
        "remote_hard_timeout_s": REMOTE_HARD_TIMEOUT_S,
        "budget_cap_usd": budget,
        "gpu_ladder": GPU_LADDER,
        "clouds": list(CLOUDS),
        "gpu_price_hint_usd_hr": GPU_PRICE_HINT_USD_HR,
        "python_on_pod": "python3.11 (pod python3 is 3.8 — do not use it)",
        "secret_handling": "RUNPOD_API_KEY + R2_* read from .env by name; never "
                           "printed/committed. Fresh RUNPOD_API_KEY required "
                           "before deploy (old key exposed, must be rotated).",
    }
    return plan, mismatches


def px_getcfg(man, *keys):
    d = man
    for k in keys:
        d = (d or {}).get(k, {}) if isinstance(d, dict) else {}
    return d if isinstance(d, str) else (d or None)


def cmd_plan(args):
    plan, mismatches = build_plan()
    os.makedirs(SMOKE_DIR, exist_ok=True)
    with open(PLAN_PATH, "w") as f:
        json.dump(plan, f, indent=2)
    print(json.dumps(plan, indent=2))
    print(f"\n[plan] written to {PLAN_PATH}", flush=True)
    if mismatches:
        print(f"[plan] WARNING: {len(mismatches)} bundle sha/bytes mismatch(es):",
              flush=True)
        for m in mismatches:
            print("  -", m)
        print("[plan] resolve mismatches before deploy (bundle drift).", flush=True)
    else:
        print("[plan] all bundle files match manifest sha256/bytes.", flush=True)


# ---------------------------------------------------------------------------
# remote run script (typed onto the pod, launched detached under nohup)
# ---------------------------------------------------------------------------
def remote_command_sequence(small_url, large_url, small_cfg, large_cfg,
                            get_bundle, get_runner, put_results, put_done):
    """Return the ordered remote command list. Values with <...> are placeholders
    in `plan`; real presigned URLs are substituted at deploy time."""
    return [
        "set -uo pipefail",
        "export PY=python3.11",   # pod python3 is 3.8 — explicit 3.11
        "mkdir -p /workspace/sam && cd /workspace/sam",
        "echo '[remote] python:' && $PY --version",
        f"curl -fsSL -o bundle.tar.gz '{get_bundle}'",
        f"curl -fsSL -o sam_smoke_runner.py '{get_runner}'",
        "mkdir -p bundle && tar -xzf bundle.tar.gz -C bundle",
        "$PY -m pip install --quiet --upgrade pip",
        "$PY -m pip install --quiet 'git+https://github.com/facebookresearch/sam2.git' "
        "numpy pillow scikit-image shapely 2>&1 | tail -3",
        # checkpoints: download, record sha256 (manifest sha is FILL_AT_DOWNLOAD_ON_POD)
        f"curl -fsSL -o sam2.1_hiera_small.pt '{small_url}'",
        "sha256sum sam2.1_hiera_small.pt | tee checkpoint_small.sha256",
        # SMALL first (manifest run_order 1)
        f"timeout {REMOTE_HARD_TIMEOUT_S}s $PY sam_smoke_runner.py --bundle bundle "
        f"--out results_gpu --checkpoint sam2.1_hiera_small.pt --model-cfg {small_cfg}; "
        "echo \"[remote] small rc=$?\" | tee results_gpu/_small_rc.txt",
        "cp -f checkpoint_small.sha256 results_gpu/ 2>/dev/null || true",
        # LARGE only if SMALL produced a results.json (manifest condition)
        "if [ -f results_gpu/results.json ]; then "
        f"curl -fsSL -o sam2.1_hiera_large.pt '{large_url}' && "
        "sha256sum sam2.1_hiera_large.pt | tee checkpoint_large.sha256 && "
        f"timeout {REMOTE_HARD_TIMEOUT_S}s $PY sam_smoke_runner.py --bundle bundle "
        f"--out results_gpu_large --checkpoint sam2.1_hiera_large.pt --model-cfg {large_cfg}; "
        "cp -f checkpoint_large.sha256 results_gpu_large/ 2>/dev/null || true; "
        "else echo '[remote] small failed — skipping large'; fi",
        # package everything that exists and ship it back
        "tar -czf results_gpu.tar.gz results_gpu $( [ -d results_gpu_large ] && "
        "echo results_gpu_large )",
        f"curl -fsS -X PUT --upload-file results_gpu.tar.gz '{put_results}'",
        # DONE marker LAST — poll waits on this
        "date -u +%Y-%m-%dT%H:%M:%SZ > DONE",
        f"curl -fsS -X PUT --upload-file DONE '{put_done}'",
        "echo '[remote] uploaded results + DONE marker'",
    ]


# ---------------------------------------------------------------------------
# DEPLOY
# ---------------------------------------------------------------------------
def create_pod_with_ladder(env, budget_cap, max_min):
    """embed_gpu ladder + boot watchdog. Returns (pod_id, cost_per_hr). Refuses
    (terminate + raise) if a booted pod's estimated cost exceeds the budget."""
    max_hr = max_min / 60.0
    for cloud in CLOUDS:
        for gpu in GPU_LADDER:
            q = ('mutation { podFindAndDeployOnDemand(input: {cloudType: %s, '
                 'gpuCount: 1, gpuTypeId: "%s", '
                 'volumeInGb: 40, volumeMountPath: "/workspace", '
                 'containerDiskInGb: 40, minVcpuCount: 4, minMemoryInGb: 24, '
                 'name: "sam-smoke-%s", imageName: "%s", '
                 'ports: "22/tcp", env: [{key: "PUBLIC_KEY", value: "%s"}]}) '
                 '{ id costPerHr } }'
                 % (cloud, gpu, PERMIT, POD_IMAGE, _pubkey().replace('"', '\\"')))
            resp = gql(q, env)
            pod = (resp.get("data") or {}).get("podFindAndDeployOnDemand")
            if not pod:
                print(f"[deploy] no capacity: {gpu} ({cloud})", flush=True)
                continue
            pod_id = pod["id"]
            cost = float(pod.get("costPerHr") or 0.0)
            # PRINT POD ID FIRST — so a human can always kill it manually.
            print(f"[deploy] POD ID = {pod_id}  ({gpu}, {cloud})  "
                  f"${cost}/hr  -> manual kill: "
                  f"python3 scripts/deploy_sam_smoke.py terminate --podid {pod_id}",
                  flush=True)
            _write_pod_state(pod_id, cost, gpu, cloud)
            # BUDGET GATE: refuse if 60-min cap would exceed the cap.
            est = cost * max_hr
            print(f"[deploy] cost check: ${cost}/hr x {max_hr:.2f}h = ${est:.3f} "
                  f"vs cap ${budget_cap}", flush=True)
            if est > budget_cap + 1e-9:
                print("[deploy] REFUSE: estimate exceeds budget cap — terminating.",
                      flush=True)
                terminate_pod(pod_id, env)
                raise SystemExit(f"budget refuse: ${est:.3f} > ${budget_cap}")
            # BOOT WATCHDOG: 8 min or hop.
            if _wait_boot(pod_id, env):
                return pod_id, cost
            print("[deploy] never booted — terminating, trying next machine",
                  flush=True)
            terminate_pod(pod_id, env)
    raise SystemExit("no GPU booted on any candidate type/cloud")


def _wait_boot(pod_id, env, minutes=8):
    for _ in range(minutes):
        time.sleep(60)
        up = pod_uptime(pod_id, env)
        print(f"[deploy] boot check pod={pod_id} uptime={up}s", flush=True)
        if up and up > 0:
            return True
    return False


def _pubkey():
    with open(SSH_KEY + ".pub") as f:
        return f.read().strip()


def _write_pod_state(pod_id, cost, gpu, cloud):
    os.makedirs(SMOKE_DIR, exist_ok=True)
    with open(POD_STATE_PATH, "w") as f:
        json.dump({"pod_id": pod_id, "cost_per_hr": cost, "gpu": gpu,
                   "cloud": cloud, "created_epoch": time.time(),
                   "max_runtime_minutes": load_manifest().get("max_runtime_minutes", 60)},
                  f, indent=2)


def cmd_deploy(args):
    man = load_manifest()
    max_min = man.get("max_runtime_minutes", 60)
    budget = man.get("budget_cap_usd", 2)
    ck = man.get("checkpoints", {})
    small_url = ck.get("small", {}).get("url")
    large_url = ck.get("large", {}).get("url")

    plan, mismatches = build_plan()
    if mismatches and not args.dry_run:
        print("[deploy] ABORT: bundle sha/bytes mismatch(es) vs manifest:")
        for m in mismatches:
            print("  -", m)
        raise SystemExit("resolve bundle drift before deploy")

    if args.dry_run:
        print("=== DRY RUN — no network call, no pod, no upload ===")
        print(f"[dry] would tarball {BUNDLE_DIR} -> {R2_BUNDLE_KEY}")
        print(f"[dry] would upload runner {RUNNER_LOCAL} -> {R2_RUNNER_KEY}")
        print(f"[dry] would presign GET bundle+runner, PUT results+DONE")
        print(f"[dry] container image: {POD_IMAGE}")
        print(f"[dry] GPU ladder x clouds (create order):")
        max_hr = max_min / 60.0
        for cloud in CLOUDS:
            for gpu in GPU_LADDER:
                est = GPU_PRICE_HINT_USD_HR.get(gpu, 0.0) * max_hr
                verdict = "OK" if est <= budget + 1e-9 else "REFUSE(>cap)"
                print(f"[dry]   {cloud:9s} {gpu:32s} ~${GPU_PRICE_HINT_USD_HR.get(gpu,0):.2f}/hr"
                      f"  x{max_hr:.2f}h = ~${est:.3f}  [{verdict}]  (cap ${budget})")
        print(f"[dry] budget cap ${budget}; remote hard timeout {REMOTE_HARD_TIMEOUT_S}s; "
              f"max runtime {max_min} min")
        print("[dry] remote command sequence (placeholder URLs):")
        for c in remote_command_sequence(
                small_url or "<small_url>", large_url or "<large_url>",
                "configs/sam2.1/sam2.1_hiera_s.yaml",
                "configs/sam2.1/sam2.1_hiera_l.yaml",
                "<GET bundle>", "<GET runner>", "<PUT results>", "<PUT done>"):
            print("    $", c)
        print("[dry] on success: leaves pod up; run `poll` to collect + auto-terminate.")
        print("[dry] on any failure before launch: try/finally terminates the pod.")
        return

    # ---- real deploy ----
    env = load_env()
    if not env.get("RUNPOD_API_KEY"):
        raise SystemExit("RUNPOD_API_KEY missing from .env (rotate + set fresh key)")

    # 1. upload inputs to R2, presign
    s3 = r2_client(env)
    tar_tmp = os.path.join(SMOKE_DIR, f"{PERMIT}_bundle.tar.gz")
    files = build_bundle_tarball(tar_tmp)
    print(f"[deploy] bundle tarball {os.path.getsize(tar_tmp)//1024} KB "
          f"({len(files)} files); uploading -> {R2_BUNDLE_KEY}", flush=True)
    s3.upload_file(tar_tmp, env["R2_BUCKET"], R2_BUNDLE_KEY)
    s3.upload_file(RUNNER_LOCAL, env["R2_BUCKET"], R2_RUNNER_KEY)
    os.remove(tar_tmp)
    get_bundle = presign(s3, env, R2_BUNDLE_KEY, "GET")
    get_runner = presign(s3, env, R2_RUNNER_KEY, "GET")
    put_results = presign(s3, env, R2_RESULTS_KEY, "PUT")
    put_done = presign(s3, env, R2_DONE_KEY, "PUT")
    # clear any stale DONE marker from a previous run
    try:
        s3.delete_object(Bucket=env["R2_BUCKET"], Key=R2_DONE_KEY)
    except Exception:
        pass
    print("[deploy] inputs uploaded + presigned (URLs not printed — they embed creds)",
          flush=True)

    # 2. create pod (ladder + watchdog + budget gate). pod id printed FIRST inside.
    pod_id = None
    try:
        pod_id, cost = create_pod_with_ladder(env, budget, max_min)
        # 3. ship + launch remote run DETACHED (nohup) so poll can take over.
        cmds = remote_command_sequence(
            small_url, large_url,
            "configs/sam2.1/sam2.1_hiera_s.yaml",
            "configs/sam2.1/sam2.1_hiera_l.yaml",
            get_bundle, get_runner, put_results, put_done)
        # newline-join (NOT &&): no `set -e`, so a failed/timed-out runner still
        # falls through to the guaranteed results+DONE upload — poll always gets
        # a signal instead of hanging until the wall-clock cap.
        remote_script = "\n".join(cmds)
        launch = [
            "cat > /workspace/sam_remote.sh <<'SAMEOF'",
            remote_script,
            "SAMEOF",
            "chmod +x /workspace/sam_remote.sh",
            "nohup bash /workspace/sam_remote.sh > /workspace/sam_run.log 2>&1 &",
            "sleep 3 && echo '[remote] launched; tail:' && tail -5 /workspace/sam_run.log",
        ]
        out, err = ssh_pty(pod_id, launch, timeout=300)
        print("---- ship/launch stdout (tail) ----")
        print(out[-2000:])
        if err.strip():
            print("---- ship/launch stderr (tail) ----")
            print(err[-600:])
        print(f"[deploy] remote run launched detached on pod {pod_id}.")
        print(f"[deploy] NEXT: python3 scripts/deploy_sam_smoke.py poll")
        print(f"[deploy] pod left RUNNING intentionally; poll terminates it at "
              f"DONE or at the {max_min}-min wall-clock cap.")
    except SystemExit:
        raise
    except Exception as e:
        # terminate-on-failure guarantee (pre-launch failures)
        if pod_id:
            print(f"[deploy] FAILURE ({e}); terminating pod {pod_id}", flush=True)
            terminate_pod(pod_id, env)
        raise


# ---------------------------------------------------------------------------
# POLL
# ---------------------------------------------------------------------------
def cmd_poll(args):
    env = load_env()
    if not os.path.exists(POD_STATE_PATH):
        raise SystemExit(f"no pod_state.json at {POD_STATE_PATH}; nothing to poll")
    st = json.load(open(POD_STATE_PATH))
    pod_id = st["pod_id"]
    max_min = st.get("max_runtime_minutes", 60)
    created = st.get("created_epoch", time.time())
    s3 = r2_client(env)
    print(f"[poll] pod {pod_id}; wall-clock cap {max_min} min; waiting on DONE "
          f"marker {R2_DONE_KEY}", flush=True)

    done = False
    try:
        while True:
            elapsed_min = (time.time() - created) / 60.0
            if _r2_exists(s3, env, R2_DONE_KEY):
                print(f"[poll] DONE marker present at {elapsed_min:.1f} min", flush=True)
                done = True
                break
            if elapsed_min >= max_min:
                print(f"[poll] WALL-CLOCK CAP hit ({elapsed_min:.1f} >= {max_min} min) "
                      "— terminating regardless of progress.", flush=True)
                break
            print(f"[poll] [{elapsed_min:.1f} min] no DONE yet; sleeping 60s", flush=True)
            time.sleep(60)
    finally:
        print(f"[poll] terminating pod {pod_id}", flush=True)
        terminate_pod(pod_id, env)

    if not done:
        raise SystemExit("timed out before DONE — pod terminated; inspect sam_run.log")

    # download + extract
    os.makedirs(RESULTS_GPU_DIR, exist_ok=True)
    tar_out = os.path.join(SMOKE_DIR, f"{PERMIT}_results_gpu.tar.gz")
    s3.download_file(env["R2_BUCKET"], R2_RESULTS_KEY, tar_out)
    print(f"[poll] downloaded {os.path.getsize(tar_out)//1024} KB results tarball",
          flush=True)
    with tarfile.open(tar_out) as tar:
        _safe_extract(tar, SMOKE_DIR)
    os.remove(tar_out)
    # remote tar packs results_gpu/ (and maybe results_gpu_large/) as top-level dirs
    print(f"[poll] extracted into {SMOKE_DIR}", flush=True)

    # verify (small first)
    if os.path.exists(VERIFY_LOCAL) and os.path.exists(
            os.path.join(RESULTS_GPU_DIR, "results.json")):
        print("[poll] running verify_sam_smoke_results.py on results_gpu/", flush=True)
        rc = subprocess.run(
            [sys.executable, VERIFY_LOCAL, "--bundle", BUNDLE_DIR,
             "--results", RESULTS_GPU_DIR]).returncode
        print(f"[poll] verify exit={rc}", flush=True)
    else:
        print("[poll] verify script or results.json absent — skipped", flush=True)
    print(f"[poll] NEXT: python3 scripts/make_sam_review_packets.py", flush=True)


def _r2_exists(s3, env, key):
    try:
        s3.head_object(Bucket=env["R2_BUCKET"], Key=key)
        return True
    except Exception:
        return False


def _safe_extract(tar, dest):
    dest = os.path.abspath(dest)
    for m in tar.getmembers():
        target = os.path.abspath(os.path.join(dest, m.name))
        if not target.startswith(dest + os.sep) and target != dest:
            raise SystemExit(f"unsafe path in tar: {m.name}")
    tar.extractall(dest)


# ---------------------------------------------------------------------------
# TERMINATE
# ---------------------------------------------------------------------------
def cmd_terminate(args):
    env = load_env()
    pod_id = args.podid
    if not pod_id and os.path.exists(POD_STATE_PATH):
        pod_id = json.load(open(POD_STATE_PATH)).get("pod_id")
    if not pod_id:
        raise SystemExit("no --podid and no pod_state.json; nothing to terminate")
    print(f"[terminate] podTerminate {pod_id}", flush=True)
    terminate_pod(pod_id, env)
    print(f"[terminate] requested termination of {pod_id}", flush=True)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("plan")
    pp.add_argument("--bundle", help="bundle dir (default: bundle/; use bundle_g1b for G1b)")
    dp = sub.add_parser("deploy")
    dp.add_argument("--dry-run", action="store_true")
    dp.add_argument("--bundle", help="bundle dir (default: bundle/; use bundle_g1b for G1b)")
    sub.add_parser("poll")
    tp = sub.add_parser("terminate")
    tp.add_argument("--podid")
    args = ap.parse_args()

    # Optional bundle override (default identical to prior behavior). The pod always
    # extracts the tarball to a dir named `bundle` and runs the runner against it,
    # which auto-detects per-task (G1b) vs viewport (G0) from tasks.json bundle_kind.
    bundle = getattr(args, "bundle", None)
    if bundle:
        global BUNDLE_DIR
        BUNDLE_DIR = bundle if os.path.isabs(bundle) else os.path.join(ROOT, bundle)

    {"plan": cmd_plan, "deploy": cmd_deploy,
     "poll": cmd_poll, "terminate": cmd_terminate}[args.cmd](args)


if __name__ == "__main__":
    main()
