#!/usr/bin/env python3
"""Chạy TRÊN MÁY BẠN. Tự bật A10 trên Lambda -> đẩy code -> chạy suy luận ->
kéo kết quả về -> TỰ TẮT MÁY.

An toàn chi phí: lệnh terminate nằm trong `finally`, nên instance vẫn được tắt
kể cả khi script lỗi giữa chừng hoặc bạn Ctrl-C. Thêm --max-minutes làm chốt chặn.

Biến môi trường bắt buộc:
  LAMBDA_API_KEY        API key ở https://cloud.lambda.ai/api-keys
  LAMBDA_SSH_KEY_NAME   tên SSH key ĐÃ đăng ký trên Lambda
  LAMBDA_SSH_KEY_PATH   đường dẫn private key tương ứng trên máy bạn
Tuỳ chọn:
  GIT_REPO_URL          repo để instance `git clone` (chỉ dùng khi --transfer git)

Ví dụ:
  python lambda/run_remote.py --dry-run
  python lambda/run_remote.py --transfer scp
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

API = "https://cloud.lambda.ai/api/v1"
INSTANCE_TYPE = "gpu_1x_a10"          # 1x A10 24GB — khoảng $0.75/giờ
ROOT = Path(__file__).resolve().parent.parent
IN_FILE = "data/11_file3_llm_input.json"
OUT_FILE = "data/12_file3_llm_verdicts.json"
REMOTE_DIR = "~/mcq"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- Lambda API
def api(method: str, path: str, key: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{API}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {e.read().decode()[:400]}") from e


def pick_region(key: str) -> str:
    data = api("GET", "/instance-types", key)["data"]
    info = data.get(INSTANCE_TYPE)
    if not info:
        raise RuntimeError(f"Tài khoản không thấy loại máy {INSTANCE_TYPE}")
    regions = [r["name"] for r in info.get("regions_with_capacity_available", [])]
    if not regions:
        raise RuntimeError(f"{INSTANCE_TYPE} hiện HẾT CHỖ ở mọi region — thử lại sau")
    log(f"region còn chỗ: {regions} -> chọn {regions[0]}")
    return regions[0]


def launch(key: str, region: str, ssh_key_name: str) -> str:
    res = api("POST", "/instance-operations/launch", key, {
        "region_name": region,
        "instance_type_name": INSTANCE_TYPE,
        "ssh_key_names": [ssh_key_name],
        "name": "mcq-qwen3vl",
    })
    iid = res["data"]["instance_ids"][0]
    log(f"đã gửi lệnh bật, instance_id={iid}")
    return iid


def wait_active(key: str, iid: str, timeout_s: int = 900) -> str:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        d = api("GET", f"/instances/{iid}", key)["data"]
        if d.get("status") == "active" and d.get("ip"):
            log(f"instance ACTIVE sau {time.time()-t0:.0f}s, ip={d['ip']}")
            return d["ip"]
        time.sleep(10)
    raise TimeoutError("instance không active kịp")


def terminate(key: str, iid: str) -> None:
    for attempt in range(3):
        try:
            api("POST", "/instance-operations/terminate", key, {"instance_ids": [iid]})
            log(f"ĐÃ TẮT instance {iid}")
            return
        except Exception as e:                                    # noqa: BLE001
            log(f"tắt máy lỗi (lần {attempt+1}/3): {e}")
            time.sleep(5)
    log(f"!!! KHÔNG TẮT ĐƯỢC {iid} — VÀO https://cloud.lambda.ai/instances TẮT TAY NGAY")


# ------------------------------------------------------------------ ssh/scp
def ssh_base(keypath: str, ip: str) -> list[str]:
    return ["ssh", "-i", keypath, "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=" + os.devnull, "-o", "ConnectTimeout=15",
            f"ubuntu@{ip}"]


def run_ssh(keypath: str, ip: str, cmd: str, check: bool = True) -> int:
    p = subprocess.run(ssh_base(keypath, ip) + [cmd])
    if check and p.returncode != 0:
        raise RuntimeError(f"lệnh remote lỗi ({p.returncode}): {cmd[:80]}")
    return p.returncode


def scp(keypath: str, src: str, dst: str) -> None:
    p = subprocess.run(["scp", "-i", keypath, "-o", "StrictHostKeyChecking=no",
                        "-o", "UserKnownHostsFile=" + os.devnull, src, dst])
    if p.returncode != 0:
        raise RuntimeError(f"scp lỗi: {src} -> {dst}")


def wait_ssh(keypath: str, ip: str, timeout_s: int = 600) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if run_ssh(keypath, ip, "true", check=False) == 0:
            log(f"SSH sẵn sàng sau {time.time()-t0:.0f}s")
            return
        time.sleep(10)
    raise TimeoutError("SSH không lên kịp")


# ------------------------------------------------------------- đẩy code lên
def push_to_github() -> str:
    repo = os.environ.get("GIT_REPO_URL", "").strip()
    if not repo:
        raise SystemExit(
            "Thiếu GIT_REPO_URL. Hoặc đặt biến này và cấu hình git remote,\n"
            "hoặc chạy với --transfer scp để copy thẳng file lên instance (không cần GitHub)."
        )
    if not (ROOT / ".git").exists():
        raise SystemExit(
            f"{ROOT} chưa phải git repo. Chạy:\n"
            f"  git init && git add . && git commit -m init && git remote add origin {repo} && git push -u origin main\n"
            "hoặc dùng --transfer scp."
        )
    log("commit & push code lên GitHub…")
    subprocess.run(["git", "-C", str(ROOT), "add", "lambda", IN_FILE], check=False)
    subprocess.run(["git", "-C", str(ROOT), "commit", "-m", "run qwen3vl shape filter"], check=False)
    p = subprocess.run(["git", "-C", str(ROOT), "push"], check=False)
    if p.returncode != 0:
        raise SystemExit("git push thất bại — kiểm tra remote/credential, hoặc dùng --transfer scp.")
    return repo


def setup_remote(keypath: str, ip: str, transfer: str, repo: str | None) -> None:
    # venv riêng: máy Lambda có scipy/numpy cài qua apt, trộn với numpy 2.x từ pip
    # sẽ gãy ("cannot import name 'Inf' from 'numpy'"). venv không thấy dist-packages.
    log("tạo venv + cài vLLM trên instance (mất vài phút)…")
    run_ssh(keypath, ip,
            "python3 -m venv ~/venv && ~/venv/bin/pip install -q --upgrade pip "
            "&& ~/venv/bin/pip install -q 'vllm>=0.11'")

    if transfer == "git":
        log("instance kéo code từ GitHub…")
        run_ssh(keypath, ip, f"rm -rf {REMOTE_DIR} && git clone --depth 1 {repo} {REMOTE_DIR}")
    else:
        log("copy code + dữ liệu thẳng lên instance…")
        run_ssh(keypath, ip, f"mkdir -p {REMOTE_DIR}/lambda {REMOTE_DIR}/data")
        scp(keypath, str(ROOT / "lambda" / "gpu_infer.py"), f"ubuntu@{ip}:{REMOTE_DIR}/lambda/")
        scp(keypath, str(ROOT / IN_FILE), f"ubuntu@{ip}:{REMOTE_DIR}/data/")


# ----------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transfer", choices=["git", "scp"], default="git",
                    help="git = push GitHub rồi instance clone; scp = copy thẳng (không cần GitHub)")
    ap.add_argument("--limit", type=int, default=0, help="chỉ chạy N câu đầu để thử")
    ap.add_argument("--max-minutes", type=int, default=90, help="chốt chặn: quá hạn thì tắt máy")
    ap.add_argument("--dry-run", action="store_true", help="chỉ kiểm tra cấu hình, KHÔNG bật máy")
    args = ap.parse_args()

    key = os.environ.get("LAMBDA_API_KEY", "").strip()
    ssh_name = os.environ.get("LAMBDA_SSH_KEY_NAME", "").strip()
    ssh_path = os.environ.get("LAMBDA_SSH_KEY_PATH", "").strip()
    missing = [n for n, v in [("LAMBDA_API_KEY", key), ("LAMBDA_SSH_KEY_NAME", ssh_name),
                              ("LAMBDA_SSH_KEY_PATH", ssh_path)] if not v]
    if missing:
        raise SystemExit("Thiếu biến môi trường: " + ", ".join(missing))
    if not Path(ssh_path).exists():
        raise SystemExit(f"Không thấy private key: {ssh_path}")
    if not (ROOT / IN_FILE).exists():
        raise SystemExit(f"Chưa có {IN_FILE} — chạy `node pipeline/11_build_file3_input.js` trước.")

    n = len(json.loads((ROOT / IN_FILE).read_text(encoding="utf-8")))
    log(f"đầu vào: {n} câu")

    region = pick_region(key)
    repo = push_to_github() if args.transfer == "git" else None

    if args.dry_run:
        log(f"DRY RUN ổn — sẽ bật {INSTANCE_TYPE} ở {region}. Không bật máy thật.")
        return 0

    iid = launch(key, region, ssh_name)
    t_start = time.time()
    try:
        ip = wait_active(key, iid)
        wait_ssh(ssh_path, ip)
        setup_remote(ssh_path, ip, args.transfer, repo)

        limit = f" --limit {args.limit}" if args.limit else ""
        log("chạy suy luận…")
        run_ssh(ssh_path, ip,
                f"cd {REMOTE_DIR} && timeout {args.max_minutes*60} "
                f"~/venv/bin/python lambda/gpu_infer.py "
                f"--input {IN_FILE} --output {OUT_FILE}{limit}")

        log("kéo kết quả về…")
        (ROOT / "data").mkdir(exist_ok=True)
        scp(ssh_path, f"ubuntu@{ip}:{REMOTE_DIR}/{OUT_FILE}", str(ROOT / OUT_FILE))
        log(f"đã lưu {OUT_FILE}")
        return 0
    finally:
        mins = (time.time() - t_start) / 60
        log(f"tổng thời gian máy chạy: {mins:.1f} phút (~${mins/60*0.75:.2f})")
        terminate(key, iid)


if __name__ == "__main__":
    sys.exit(main())
