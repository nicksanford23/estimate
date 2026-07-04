#!/usr/bin/env python3
"""Orchestrate a one-shot RunPod GPU embedding run.

Local side: tar all rendered page PNGs + manifest -> R2 claude-repo/embed_in/,
upload bootstrap, create an RTX 4090 community pod that runs embed_remote.sh,
poll R2 for the DONE marker, download the three .npz embedding files to
data/embeddings/, terminate pod (belt-and-braces; it self-destructs too).

Usage: python3 scripts/embed_gpu.py <run_tag>
"""
import json
import os
import sqlite3
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = {}
with open(os.path.join(ROOT, ".env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            ENV[k] = v

TAG = sys.argv[1] if len(sys.argv) > 1 else "run1"
S3 = ["--aws-sigv4", "aws:amz:auto:s3", "--user",
      f"{ENV['R2_ACCESS_KEY_ID']}:{ENV['R2_SECRET_ACCESS_KEY']}"]
BASE = f"{ENV['R2_ENDPOINT']}/{ENV['R2_BUCKET']}/claude-repo"
GQL = "https://api.runpod.io/graphql"
AUTH = {"Authorization": f"Bearer {ENV['RUNPOD_API_KEY']}"}


def curl(args, timeout=1800):
    r = subprocess.run(["curl", "-s", "-m", str(timeout)] + args,
                       capture_output=True, timeout=timeout + 60)
    return r.stdout.decode()


def gql(query):
    r = subprocess.run(
        ["curl", "-s", "-m", "60", "-X", "POST", GQL,
         "-H", "content-type: application/json",
         "-H", f"Authorization: Bearer {ENV['RUNPOD_API_KEY']}",
         "-d", json.dumps({"query": query})], capture_output=True, timeout=90)
    return json.loads(r.stdout.decode())


def main():
    if "podonly" in sys.argv:
        launch_pod_and_poll()
        return
    db = sqlite3.connect(os.path.join(ROOT, "data", "estimate.db"))
    rows = db.execute("SELECT id, image_path FROM page ORDER BY id").fetchall()
    man = os.path.join(ROOT, "data", f"{TAG}_manifest.csv")
    with open(man, "w") as f:
        for pid, path in rows:
            f.write(f"{pid},{path}\n")
    print(f"manifest: {len(rows)} pages", flush=True)

    tar = os.path.join(ROOT, "data", f"{TAG}_pages.tar")
    filelist = os.path.join(ROOT, "data", f"{TAG}_files.txt")
    with open(filelist, "w") as f:
        for _, path in rows:
            f.write(path + "\n")
    subprocess.run(["tar", "-cf", tar, "-C", ROOT, "-T", filelist], check=True)
    os.remove(filelist)
    print(f"tar: {os.path.getsize(tar)//1048576} MB; uploading...", flush=True)
    import boto3
    from boto3.s3.transfer import TransferConfig
    s3 = boto3.client("s3", endpoint_url=ENV["R2_ENDPOINT"],
                      aws_access_key_id=ENV["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=ENV["R2_SECRET_ACCESS_KEY"],
                      region_name="auto")
    cfg = TransferConfig(multipart_threshold=64 * 1024 * 1024,
                         multipart_chunksize=64 * 1024 * 1024, max_concurrency=4)
    for path, key in [(tar, f"{TAG}_pages.tar"), (man, f"{TAG}_manifest.csv"),
                      (os.path.join(ROOT, "scripts", "embed_remote.sh"), "bootstrap.sh")]:
        s3.upload_file(path, ENV["R2_BUCKET"], f"claude-repo/embed_in/{key}", Config=cfg)
        print(f"uploaded {key}", flush=True)
    os.remove(tar)
    print("uploaded; creating pod...", flush=True)
    launch_pod_and_poll()


def launch_pod_and_poll():
    docker_args = (
        "bash -c 'curl -s --aws-sigv4 aws:amz:auto:s3 --user $R2_AK:$R2_SK "
        "-o /b.sh $R2_EP/$R2_BUCKET/claude-repo/embed_in/bootstrap.sh && bash /b.sh'")
    env_pairs = [("R2_EP", ENV["R2_ENDPOINT"]), ("R2_BUCKET", ENV["R2_BUCKET"]),
                 ("R2_AK", ENV["R2_ACCESS_KEY_ID"]), ("R2_SK", ENV["R2_SECRET_ACCESS_KEY"]),
                 ("RUN_TAG", TAG)]
    env_gql = ",".join('{key: "%s", value: "%s"}' % p for p in env_pairs)
    candidates = [(cloud, gpu)
                  for cloud in ("SECURE", "COMMUNITY")
                  for gpu in ("NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 3090",
                              "NVIDIA RTX A5000", "NVIDIA RTX A4500", "NVIDIA L4",
                              "NVIDIA RTX 4000 Ada Generation")]
    pod = None
    for cloud, gpu in candidates:
        q = ('mutation { podFindAndDeployOnDemand(input: {cloudType: %s, '
             'gpuCount: 1, gpuTypeId: "%s", '
             'volumeInGb: 30, volumeMountPath: "/workspace", containerDiskInGb: 30, '
             'minVcpuCount: 4, minMemoryInGb: 16, '
             'name: "embed-%s", imageName: '
             '"runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04", '
             'dockerArgs: "%s", env: [%s]}) { id costPerHr } }'
             % (cloud, gpu, TAG, docker_args.replace('"', '\\"'), env_gql))
        resp = gql(q)
        pod = resp.get("data", {}).get("podFindAndDeployOnDemand")
        if not pod:
            print(f"no capacity: {gpu} ({cloud})", flush=True)
            continue
        print(f"pod {pod['id']} ({gpu}, {cloud}) at ${pod['costPerHr']}/hr", flush=True)
        # boot watchdog: a community machine can accept the rent yet never
        # start the container (uptime stays <= 0). Give it 8 min, else hop.
        booted = False
        for _ in range(8):
            time.sleep(60)
            r = gql('query { pod(input: {podId: "%s"}) '
                    '{ runtime { uptimeInSeconds } } }' % pod["id"])
            up = ((r.get("data") or {}).get("pod") or {}).get("runtime") or {}
            up = up.get("uptimeInSeconds") or 0
            print(f"boot check: uptime={up}s", flush=True)
            if up > 0:
                booted = True
                break
        if booted:
            break
        print("never booted — terminating, trying next machine", flush=True)
        gql('mutation { podTerminate(input: {podId: "%s"}) }' % pod["id"])
        pod = None
    assert pod, "no GPU booted on any candidate type"

    t0 = time.time()
    try:
        while time.time() - t0 < 5400:
            time.sleep(60)
            code = curl(S3 + ["-o", "/dev/null", "-w", "%{http_code}", "-I",
                              f"{BASE}/embed_out/{TAG}_DONE"], 60)
            print(f"[{int(time.time()-t0)}s] done-marker: {code.strip()}", flush=True)
            if code.strip() == "200":
                break
        else:
            raise TimeoutError("embedding pod timed out after 90 min")
        os.makedirs(os.path.join(ROOT, "data", "embeddings"), exist_ok=True)
        for f in ["clip_vitl14", "siglip_b16", "dinov2_vitb14"]:
            out = os.path.join(ROOT, "data", "embeddings", f"{TAG}_{f}.npz")
            curl(S3 + ["-o", out, f"{BASE}/embed_out/{TAG}_{f}.npz"])
            print(f, os.path.getsize(out) // 1048576, "MB", flush=True)
    finally:
        gql('mutation { podTerminate(input: {podId: "%s"}) }' % pod["id"])
        print("pod terminated", flush=True)


if __name__ == "__main__":
    main()
