#!/usr/bin/env python3
"""Lean G1 deploy: one on-demand GPU pod runs SAM 2.1 Small over the
24-06748-RNVS smoke bundle, results come back via R2, pod terminates.

Pattern is scripts/embed_gpu.py (proven GPU run: GraphQL ladder, R2
bootstrap via dockerArgs, boot watchdog, done-marker polling, terminate in
finally) with STATE.md failed-attempt guards: volumeMountPath always set
with volumeInGb; hard wall-clock cap; pod id printed first so a human can
kill it; results verified locally before declaring success.

Budget: cap $2. Runtime: cap 45 min then force-terminate.
"""
import json, os, subprocess, sys, tarfile, time, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMOKE = os.path.join(ROOT, "data", "sam_smoke", "24-06748-RNVS")
BUNDLE = os.path.join(SMOKE, "bundle")
IN_PREFIX = "claude-repo/sam_smoke_in"
OUT_PREFIX = "claude-repo/sam_smoke_out"
MAX_SECONDS = 45 * 60
BUDGET_USD = 2.0
CKPT_URL = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt"
MODEL_CFG = "configs/sam2.1/sam2.1_hiera_s.yaml"


def load_env():
    env = {}
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


ENV = load_env()


def gql(q):
    r = subprocess.run(
        ["curl", "-s", "-m", "60", "https://api.runpod.io/graphql",
         "-H", f"Authorization: Bearer {ENV['RUNPOD_API_KEY']}",
         "-H", "content-type: application/json",
         "-d", json.dumps({"query": q})],
        capture_output=True, timeout=90)
    return json.loads(r.stdout.decode() or "{}")


def s3():
    import boto3
    return boto3.client("s3", endpoint_url=ENV["R2_ENDPOINT"],
                        aws_access_key_id=ENV["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=ENV["R2_SECRET_ACCESS_KEY"],
                        region_name="auto")


BOOTSTRAP = r"""#!/bin/bash
cd /workspace
exec > >(tee /workspace/boot.log) 2>&1
set -x
S3PUT() { curl -s --retry 3 --aws-sigv4 aws:amz:auto:s3 --user "$R2_AK:$R2_SK" -T "$1" "$R2_EP/$R2_BUCKET/$2"; }
uplog() { S3PUT /workspace/boot.log claude-repo/sam_smoke_out/boot.log || true; }
trap uplog EXIT
( while true; do sleep 30; uplog; done ) &
pip install -q "git+https://github.com/facebookresearch/sam2.git" scikit-image shapely || exit 1
curl -sL --retry 3 -o sam2.1_hiera_small.pt CKPT_URL_SUB || exit 1
sha256sum sam2.1_hiera_small.pt
curl -s --retry 3 --aws-sigv4 aws:amz:auto:s3 --user "$R2_AK:$R2_SK" -o bundle.tar.gz "$R2_EP/$R2_BUCKET/claude-repo/sam_smoke_in/bundle.tar.gz" || exit 1
tar xzf bundle.tar.gz
python sam_smoke_runner.py --bundle bundle --out results_gpu --checkpoint sam2.1_hiera_small.pt --model-cfg MODEL_CFG_SUB || exit 1
tar czf results_gpu.tar.gz results_gpu
S3PUT results_gpu.tar.gz claude-repo/sam_smoke_out/results_gpu.tar.gz || exit 1
echo done > DONE_MARK
S3PUT DONE_MARK claude-repo/sam_smoke_out/SMOKE_DONE
""".replace("CKPT_URL_SUB", CKPT_URL).replace("MODEL_CFG_SUB", MODEL_CFG)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prep_and_upload():
    tar_path = os.path.join(SMOKE, "bundle_upload.tar.gz")
    with tarfile.open(tar_path, "w:gz") as t:
        t.add(BUNDLE, arcname="bundle")
        t.add(os.path.join(ROOT, "scripts", "sam_smoke_runner.py"),
              arcname="sam_smoke_runner.py")
    plan = {
        "bundle_tar_sha256": sha256(tar_path),
        "checkpoint_url": CKPT_URL, "model_cfg": MODEL_CFG,
        "image": "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
        "max_seconds": MAX_SECONDS, "budget_usd": BUDGET_USD,
        "in": IN_PREFIX, "out": OUT_PREFIX,
        "started_at_epoch": time.time(),
    }
    with open(os.path.join(SMOKE, "deploy_plan.json"), "w") as f:
        json.dump(plan, f, indent=1)
    print("deploy plan recorded:", json.dumps(plan, indent=1), flush=True)
    c = s3()
    # clear stale outputs so the DONE marker can't be a ghost from a past run
    for k in ("SMOKE_DONE", "results_gpu.tar.gz", "boot.log"):
        try:
            c.delete_object(Bucket=ENV["R2_BUCKET"], Key=f"{OUT_PREFIX}/{k}")
        except Exception:
            pass
    c.upload_file(tar_path, ENV["R2_BUCKET"], f"{IN_PREFIX}/bundle.tar.gz")
    boot = os.path.join(SMOKE, "bootstrap.sh")
    with open(boot, "w") as f:
        f.write(BOOTSTRAP)
    c.upload_file(boot, ENV["R2_BUCKET"], f"{IN_PREFIX}/bootstrap.sh")
    print("uploaded bundle + bootstrap to R2", flush=True)


def create_pod():
    docker_args = (
        "bash -c 'curl -s --aws-sigv4 aws:amz:auto:s3 --user $R2_AK:$R2_SK "
        f"-o /b.sh $R2_EP/$R2_BUCKET/{IN_PREFIX}/bootstrap.sh && bash /b.sh'")
    env_pairs = [("R2_EP", ENV["R2_ENDPOINT"]), ("R2_BUCKET", ENV["R2_BUCKET"]),
                 ("R2_AK", ENV["R2_ACCESS_KEY_ID"]), ("R2_SK", ENV["R2_SECRET_ACCESS_KEY"])]
    env_gql = ",".join('{key: "%s", value: "%s"}' % p for p in env_pairs)
    candidates = [(cloud, gpu)
                  for cloud in ("SECURE", "COMMUNITY")
                  for gpu in ("NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 3090",
                              "NVIDIA RTX A5000", "NVIDIA RTX A4500", "NVIDIA L4",
                              "NVIDIA RTX 4000 Ada Generation")]
    for cloud, gpu in candidates:
        q = ('mutation { podFindAndDeployOnDemand(input: {cloudType: %s, '
             'gpuCount: 1, gpuTypeId: "%s", '
             'volumeInGb: 30, volumeMountPath: "/workspace", containerDiskInGb: 30, '
             'minVcpuCount: 4, minMemoryInGb: 16, name: "sam-smoke", imageName: '
             '"runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04", '
             'dockerArgs: "%s", env: [%s]}) { id costPerHr } }'
             % (cloud, gpu, docker_args.replace('"', '\\"'), env_gql))
        resp = gql(q)
        pod = (resp.get("data") or {}).get("podFindAndDeployOnDemand")
        if not pod:
            print(f"no capacity: {gpu} ({cloud})", flush=True)
            continue
        cost = float(pod.get("costPerHr") or 9)
        print(f"POD ID (kill manually if I die): {pod['id']}  "
              f"({gpu}, {cloud}) ${cost}/hr", flush=True)
        if cost * (MAX_SECONDS / 3600.0) > BUDGET_USD:
            print("over budget cap, terminating + next", flush=True)
            gql('mutation { podTerminate(input: {podId: "%s"}) }' % pod["id"])
            continue
        # boot watchdog (STATE.md: created != working)
        for i in range(8):
            time.sleep(60)
            r = gql('query { pod(input: {podId: "%s"}) '
                    '{ runtime { uptimeInSeconds } } }' % pod["id"])
            up = (((r.get("data") or {}).get("pod") or {}).get("runtime")
                  or {}).get("uptimeInSeconds") or 0
            print(f"boot check {i}: uptime={up}s", flush=True)
            if up > 0:
                return pod["id"]
        print("never booted; terminating, next candidate", flush=True)
        gql('mutation { podTerminate(input: {podId: "%s"}) }' % pod["id"])
    raise SystemExit("no GPU booted on any candidate")


def poll_and_fetch(pid):
    c = s3()
    t0 = time.time()
    while time.time() - t0 < MAX_SECONDS:
        time.sleep(30)
        try:
            c.head_object(Bucket=ENV["R2_BUCKET"], Key=f"{OUT_PREFIX}/SMOKE_DONE")
            print(f"[{int(time.time()-t0)}s] DONE marker found", flush=True)
            break
        except Exception:
            print(f"[{int(time.time()-t0)}s] waiting...", flush=True)
    else:
        # salvage the boot log for diagnosis before the cap kills the run
        try:
            c.download_file(ENV["R2_BUCKET"], f"{OUT_PREFIX}/boot.log",
                            os.path.join(SMOKE, "boot.log"))
        except Exception:
            pass
        raise TimeoutError("hit 45-min cap without DONE marker")
    out_tar = os.path.join(SMOKE, "results_gpu.tar.gz")
    c.download_file(ENV["R2_BUCKET"], f"{OUT_PREFIX}/results_gpu.tar.gz", out_tar)
    with tarfile.open(out_tar) as t:
        t.extractall(SMOKE)
    try:
        c.download_file(ENV["R2_BUCKET"], f"{OUT_PREFIX}/boot.log",
                        os.path.join(SMOKE, "boot.log"))
    except Exception:
        pass
    print("results extracted to", os.path.join(SMOKE, "results_gpu"), flush=True)
    v = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "verify_sam_smoke_results.py"),
                        "--bundle", BUNDLE,
                        "--results", os.path.join(SMOKE, "results_gpu")],
                       capture_output=True)
    print(v.stdout.decode(), v.stderr.decode(), flush=True)


def main():
    prep_and_upload()
    pid = create_pod()
    try:
        poll_and_fetch(pid)
    finally:
        gql('mutation { podTerminate(input: {podId: "%s"}) }' % pid)
        print(f"pod {pid} terminated", flush=True)


if __name__ == "__main__":
    main()
