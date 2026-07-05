#!/usr/bin/env python3
"""Deploy the Model-1 v1 demo to a RunPod CPU pod (the live, always-on demo).

Why this shape (hard-won, see STATE.md "Failed Attempts"):
  * GraphQL `dockerArgs` is broken on this account -> we never use it. Instead
    we deploy a stock RunPod base image (which boots sshd + injects our key),
    then start the app by TYPING commands into the pod over the account SSH
    proxy (PTY pipe trick). No custom container needed.
  * The pod's old `curl` can't sign R2 SigV4, so we ship code as presigned R2
    GET URLs (boto3 generate_presigned_url) and the pod just curls them.
  * CPU pod (not GPU): REST v1 create with computeType=CPU, cpuFlavorIds=
    ["cpu3c"] (cheapest compute-optimized), vcpuCount=2 -> ~$0.06/hr, 4GB RAM.

Lifecycle
  create : REST POST https://rest.runpod.io/v1/pods
  ship   : upload app.py / model_v1_lib.py / model_v1.joblib to
           claude-repo/deploy/, presign, curl them onto the pod
  start  : pip install deps, launch `uvicorn app:app --port 8000`
  verify : curl https://<podId>-8000.proxy.runpod.net/health from here
  App reachable at https://<podId>-8000.proxy.runpod.net
  Stop with: python3 scripts/deploy_pod.py terminate --podid <id>
             (or GraphQL podTerminate)

Usage
  python3 scripts/deploy_pod.py create                 # -> prints pod id
  python3 scripts/deploy_pod.py ship-start --podid ID  # ship code + start app
  python3 scripts/deploy_pod.py verify --podid ID
  python3 scripts/deploy_pod.py terminate --podid ID
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSH_ACCOUNT_SUFFIX = "644115c8"          # this account's ssh.runpod.io proxy id
SSH_KEY = os.path.expanduser("~/.ssh/runpod_ed25519")
CPU_FLAVOR = "cpu3c"
VCPU = 2
IMAGE = "runpod/base:0.6.2-cpu"
DEPLOY_PREFIX = "claude-repo/deploy"
SHIP = {
    "app.py": os.path.join(ROOT, "scripts", "app.py"),
    "model_v1_lib.py": os.path.join(ROOT, "scripts", "model_v1_lib.py"),
    "model_v1.joblib": os.path.join(ROOT, "models", "model_v1.joblib"),
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


def create_pod():
    pub = open(SSH_KEY + ".pub").read().strip()
    body = {
        "name": "flooring-v1-demo",
        "computeType": "CPU",
        "cpuFlavorIds": [CPU_FLAVOR],
        "vcpuCount": VCPU,
        "cloudType": "SECURE",
        "imageName": IMAGE,
        "containerDiskInGb": 15,
        "ports": ["8000/http", "22/tcp"],
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
    print(f"pod {pid} ({CPU_FLAVOR}, {VCPU} vCPU) ${d.get('costPerHr')}/hr "
          f"image={d.get('imageName')}")
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
            "get_object", Params={"Bucket": ENV["R2_BUCKET"], "Key": key},
            ExpiresIn=7200)
    return urls


def ssh_pty(pid, commands, timeout=600):
    """Type `commands` (list[str]) into the pod shell over the account SSH
    proxy (PTY pipe trick). Returns (stdout, stderr)."""
    user = f"{pid}-{SSH_ACCOUNT_SUFFIX}@ssh.runpod.io"
    payload = "".join(f"{c}\n" for c in commands) + "exit\n"
    p = subprocess.run(
        ["ssh", "-tt", "-o", "StrictHostKeyChecking=no",
         "-o", "UserKnownHostsFile=/dev/null", "-i", SSH_KEY, user],
        input=payload.encode(), capture_output=True, timeout=timeout)
    return p.stdout.decode(errors="ignore"), p.stderr.decode(errors="ignore")


def ship_start(pid):
    urls = upload_and_presign()
    cmds = [
        "mkdir -p /app/models && cd /app",
        f"curl -s -L -o /app/app.py '{urls['app.py']}'",
        f"curl -s -L -o /app/model_v1_lib.py '{urls['model_v1_lib.py']}'",
        f"curl -s -L -o /app/models/model_v1.joblib '{urls['model_v1.joblib']}'",
        "pip install -q fastapi 'uvicorn[standard]' 'scikit-learn==1.9.0' "
        "scipy numpy pymupdf boto3 joblib python-multipart 2>&1 | tail -2",
        "pkill -f 'uvicorn app:app' 2>/dev/null; sleep 1",
        "cd /app && nohup uvicorn app:app --host 0.0.0.0 --port 8000 "
        "> /app/uvicorn.log 2>&1 &",
        "sleep 10 && curl -s localhost:8000/health && echo",
    ]
    out, err = ssh_pty(pid, cmds)
    print("---- remote stdout ----")
    print(out[-3000:])
    if err.strip():
        print("---- remote stderr (tail) ----")
        print(err[-800:])


def verify(pid):
    base = f"https://{pid}-8000.proxy.runpod.net"
    print(f"GET {base}/health")
    h = subprocess.run(["curl", "-s", "-m", "40", f"{base}/health"],
                       capture_output=True, timeout=60).stdout.decode()
    print(h)
    return h


def terminate(pid):
    print(rest("DELETE", f"/pods/{pid}"))
    print(f"terminated {pid}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["create", "wait", "ship-start", "verify", "terminate"])
    ap.add_argument("--podid")
    a = ap.parse_args()
    if a.action == "create":
        print(create_pod())
    elif a.action == "wait":
        print("booted" if wait_boot(a.podid) else "TIMEOUT")
    elif a.action == "ship-start":
        ship_start(a.podid)
    elif a.action == "verify":
        verify(a.podid)
    elif a.action == "terminate":
        terminate(a.podid)


if __name__ == "__main__":
    main()
