#!/usr/bin/env python3
"""Probe 30 Phase 1 pod ops -- CPU pod for feature extraction (speed
directive: move extraction off the shared 2-core box). Same proven pattern
as scripts/deploy_pod.py (REST create, SSH-PTY command typing, presigned R2
GET URLs for shipping code -- pod curl can't sign SigV4).

Usage:
  python3 scripts/probe30_pod_extract.py create --vcpu 16
  python3 scripts/probe30_pod_extract.py ship-run --podid ID --workers 14
  python3 scripts/probe30_pod_extract.py status --podid ID
  python3 scripts/probe30_pod_extract.py terminate --podid ID
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSH_ACCOUNT_SUFFIX = "644115c8"
SSH_KEY = os.path.expanduser("~/.ssh/runpod_ed25519")
CPU_FLAVOR = "cpu3c"
IMAGE = "runpod/base:0.6.2-cpu"
DEPLOY_PREFIX = "claude-repo/probe30_deploy"
SHIP = {
    "probe30_extract_worker.py": os.path.join(ROOT, "scripts", "probe30_extract_worker.py"),
    "all_pages.csv": os.path.join(ROOT, "data", "probe30", "all_pages.csv"),
}


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


def rest(method, path, body=None, timeout=120):
    args = ["curl", "-s", "-m", str(timeout), "-X", method,
            f"https://rest.runpod.io/v1{path}",
            "-H", f"Authorization: Bearer {ENV['RUNPOD_API_KEY']}",
            "-H", "content-type: application/json"]
    if body is not None:
        args += ["-d", json.dumps(body)]
    r = subprocess.run(args, capture_output=True, timeout=timeout + 30)
    return r.stdout.decode()


def create_pod(vcpu=16):
    pub = open(SSH_KEY + ".pub").read().strip()
    body = {
        "name": "probe30-feature-extract",
        "computeType": "CPU",
        "cpuFlavorIds": [CPU_FLAVOR],
        "vcpuCount": vcpu,
        "cloudType": "SECURE",
        "imageName": IMAGE,
        "containerDiskInGb": 20,
        "ports": ["22/tcp"],
        "env": {
            "PUBLIC_KEY": pub,
            "R2_ENDPOINT": ENV["R2_ENDPOINT"],
            "R2_ACCESS_KEY_ID": ENV["R2_ACCESS_KEY_ID"],
            "R2_SECRET_ACCESS_KEY": ENV["R2_SECRET_ACCESS_KEY"],
            "R2_BUCKET": ENV["R2_BUCKET"],
        },
    }
    d = json.loads(rest("POST", "/pods", body))
    pid = d.get("id")
    print(f"pod {pid} ({CPU_FLAVOR}, {vcpu} vCPU) ${d.get('costPerHr')}/hr image={d.get('imageName')}")
    return pid


def wait_boot(pid, minutes=8):
    for i in range(minutes * 4):
        d = json.loads(rest("GET", f"/pods/{pid}"))
        rt = d.get("runtime") or {}
        up = rt.get("uptimeInSeconds")
        print(f"[{i*15}s] status={d.get('desiredStatus')} uptime={up}", flush=True)
        if up and up > 0:
            return True
        time.sleep(15)
    return False


def upload_and_presign():
    import boto3
    s3 = boto3.client("s3", endpoint_url=ENV["R2_ENDPOINT"],
                      aws_access_key_id=ENV["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=ENV["R2_SECRET_ACCESS_KEY"],
                      region_name="auto")
    urls = {}
    for name, path in SHIP.items():
        key = f"{DEPLOY_PREFIX}/{name}"
        s3.upload_file(path, ENV["R2_BUCKET"], key)
        urls[name] = s3.generate_presigned_url(
            "get_object", Params={"Bucket": ENV["R2_BUCKET"], "Key": key}, ExpiresIn=14400)
    return urls


def ssh_pty(pid, commands, timeout=1800):
    user = f"{pid}-{SSH_ACCOUNT_SUFFIX}@ssh.runpod.io"
    payload = "".join(f"{c}\n" for c in commands) + "exit\n"
    p = subprocess.run(
        ["ssh", "-tt", "-o", "StrictHostKeyChecking=no",
         "-o", "UserKnownHostsFile=/dev/null", "-i", SSH_KEY, user],
        input=payload.encode(), capture_output=True, timeout=timeout)
    return p.stdout.decode(errors="ignore"), p.stderr.decode(errors="ignore")


def ship_run(pid, workers=14, background=True):
    urls = upload_and_presign()
    cmds = [
        "mkdir -p /app && cd /app",
        f"curl -s -L -o /app/probe30_extract_worker.py '{urls['probe30_extract_worker.py']}'",
        f"curl -s -L -o /app/all_pages.csv '{urls['all_pages.csv']}'",
        "pip install -q pymupdf boto3 numpy scipy 2>&1 | tail -3",
        "cd /app && nohup python3.11 probe30_extract_worker.py --roster all_pages.csv "
        f"--workers {workers} --out-prefix claude-repo/probe30_features "
        "> /app/extract.log 2>&1 &",
        "sleep 20 && tail -40 /app/extract.log",
    ]
    out, err = ssh_pty(pid, cmds, timeout=300)
    print("---- remote stdout ----")
    print(out[-4000:])
    if err.strip():
        print("---- remote stderr (tail) ----")
        print(err[-1000:])


def status(pid):
    out, err = ssh_pty(pid, ["tail -80 /app/extract.log", "echo ---PROC---",
                              "pgrep -fa probe30_extract_worker.py | wc -l"], timeout=60)
    print(out[-5000:])


def terminate(pid):
    print(rest("DELETE", f"/pods/{pid}"))
    print(f"terminated {pid}")


def verify_terminated():
    d = json.loads(rest("GET", "/pods"))
    print(json.dumps([{"id": p["id"], "name": p["name"], "status": p["desiredStatus"]} for p in d], indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["create", "wait", "ship-run", "status", "terminate", "verify"])
    ap.add_argument("--podid")
    ap.add_argument("--vcpu", type=int, default=16)
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    if a.action == "create":
        print(create_pod(a.vcpu))
    elif a.action == "wait":
        print("booted" if wait_boot(a.podid) else "TIMEOUT")
    elif a.action == "ship-run":
        ship_run(a.podid, a.workers)
    elif a.action == "status":
        status(a.podid)
    elif a.action == "terminate":
        terminate(a.podid)
    elif a.action == "verify":
        verify_terminated()


if __name__ == "__main__":
    main()
