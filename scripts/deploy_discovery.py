#!/usr/bin/env python3
"""Deploy the One Stop discovery sweep to a cheap RunPod CPU pod.

Same hard-won shape as deploy_pod.py (see its docstring + STATE.md):
REST v1 create (computeType=CPU, cpu3c, 2 vCPU ~$0.06/hr), stock
runpod/base image boots sshd, files ship as presigned R2 GETs curled from the
pod, processes start by typing over the account SSH proxy. GraphQL dockerArgs
stays unused (broken on this account). proxies.txt (credentials) is NOT
staged in R2 — it is typed over SSH as base64.

The pod runs scripts/pod_supervisor.py, which mirrors results to Neon and
terminates the pod itself when done — nothing here needs to stay alive.

Usage
  python3 scripts/deploy_discovery.py create
  python3 scripts/deploy_discovery.py wait --podid ID
  python3 scripts/deploy_discovery.py ship-start --podid ID
  python3 scripts/deploy_discovery.py check --podid ID   # remote log tail
  python3 scripts/deploy_discovery.py terminate --podid ID
"""
import argparse
import base64
import json
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSH_ACCOUNT_SUFFIX = "644115c8"
SSH_KEY = os.path.expanduser("~/.ssh/runpod_ed25519")
CPU_FLAVOR = "cpu3c"
VCPU = 2
IMAGE = "runpod/base:0.6.2-cpu"
DEPLOY_PREFIX = "claude-repo/deploy/discovery"
SHIP = {  # name on pod (under /app) -> local path; NO credentials in here
    "discover_docs.py": os.path.join(ROOT, "scripts", "discover_docs.py"),
    "pod_supervisor.py": os.path.join(ROOT, "scripts", "pod_supervisor.py"),
    "discover_targets.csv": os.path.join(ROOT, "data", "discover_targets.csv"),
    "discovered_docs.csv": os.path.join(ROOT, "data", "discovered_docs.csv"),
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
        "name": "onestop-discovery",
        "computeType": "CPU",
        "cpuFlavorIds": [CPU_FLAVOR],
        "vcpuCount": VCPU,
        "cloudType": "SECURE",
        "imageName": IMAGE,
        "containerDiskInGb": 15,
        "ports": ["22/tcp"],
        "env": {
            "PUBLIC_KEY": pub,
            "NEON_DATABASE_URL": ENV["NEON_DATABASE_URL"],
            "RUNPOD_API_KEY": ENV["RUNPOD_API_KEY"],
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
    user = f"{pid}-{SSH_ACCOUNT_SUFFIX}@ssh.runpod.io"
    payload = "".join(f"{c}\n" for c in commands) + "exit\n"
    p = subprocess.run(
        ["ssh", "-tt", "-o", "StrictHostKeyChecking=no",
         "-o", "UserKnownHostsFile=/dev/null", "-i", SSH_KEY, user],
        input=payload.encode(), capture_output=True, timeout=timeout)
    return p.stdout.decode(errors="ignore"), p.stderr.decode(errors="ignore")


def ship_start(pid):
    urls = upload_and_presign()
    proxies_b64 = base64.b64encode(
        open(os.path.join(ROOT, "data", "proxies.txt"), "rb").read()).decode()
    cmds = ["mkdir -p /app && cd /app"]
    cmds += [f"curl -s -L -o /app/{name} '{url}'" for name, url in urls.items()]
    cmds += [
        f"echo {proxies_b64} | base64 -d > /app/proxies.txt",
        "wc -l /app/*.csv /app/proxies.txt && head -c 60 /app/discover_docs.py && echo",
        "pip install -q psycopg2-binary 2>&1 | tail -1",
        "cd /app && nohup python3 -u pod_supervisor.py > /app/supervisor.log 2>&1 &",
        "sleep 20 && tail -5 /app/supervisor.log && tail -3 /app/run.log 2>/dev/null",
    ]
    out, err = ssh_pty(pid, cmds)
    print("---- remote stdout ----")
    print(out[-4000:])
    if err.strip():
        print("---- remote stderr (tail) ----")
        print(err[-800:])


def check(pid):
    out, _ = ssh_pty(pid, [
        "tail -15 /app/supervisor.log 2>/dev/null",
        "echo ---run.log---",
        "tail -5 /app/run.log 2>/dev/null",
        "echo ---csv---; wc -l /app/discovered_docs.csv",
    ], timeout=120)
    print(out[-3000:])


def terminate(pid):
    print(rest("DELETE", f"/pods/{pid}"))
    print(f"terminated {pid}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["create", "wait", "ship-start", "check", "terminate"])
    ap.add_argument("--podid")
    a = ap.parse_args()
    if a.action == "create":
        print(create_pod())
    elif a.action == "wait":
        print("booted" if wait_boot(a.podid) else "TIMEOUT")
    elif a.action == "ship-start":
        ship_start(a.podid)
    elif a.action == "check":
        check(a.podid)
    elif a.action == "terminate":
        terminate(a.podid)


if __name__ == "__main__":
    main()
