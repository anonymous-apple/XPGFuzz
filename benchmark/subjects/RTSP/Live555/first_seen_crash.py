#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
first_seen_crash.py (Python 3.8+)

Goal:
  - Replay AFLNet "replayable-crashes" seeds
  - Deduplicate *real* crashes using robust signatures (especially ASAN)
  - Report "first seen" time per unique crash by seed mtime

Key features:
  1) Skip README.txt by default; only include AFLNet seeds by filename regex (default: ^id:)
  2) Avoid false positives caused by killing the server ourselves
  3) Strong crash detection: ASAN/UBSAN/SEGV/ABORT/assert, etc.
  4) ASAN signature parsing:
       - bug type (stack-buffer-overflow, heap-use-after-free, ...)
       - READ/WRITE + size
       - pc0 offset (+ optional pc1)
       - stack overflow variable name + line (if present)
       - frame offset (if present)
       - heap UAF alloc/free top frame offset (if present)
  5) Writes report.{txt,csv,json} + per-seed logs

Usage example:
  python3 first_seen_crash.py \
    --out-dir /home/ubuntu/experiments/out-live555-aflnet-1 \
    --subdir replayable-crashes \
    --proto RTSP \
    --port 8554 \
    --server-cmd "./live555/testProgs/testOnDemandRTSPServer 8554" \
    --replay-bin /home/ubuntu/aflnet/aflnet-replay

Optional:
  --seed-regex '^id:'         only include AFLNet-style seeds (default)
  --seed-regex '.*'           include all files (not recommended)
  --include-readme            include README.txt (default: off)
  --keep-nonrepro             keep non-crash entries in per_seed json
  --replay-timeout 8          seconds
  --server-start-timeout 3
  --server-grace 1
  --tz America/Los_Angeles
"""

import argparse
import csv
import dataclasses
import hashlib
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Timezone support (py3.8 friendly)
# -----------------------------
ZoneInfo = None
try:
    from zoneinfo import ZoneInfo as _ZI  # py3.9+
    ZoneInfo = _ZI
except Exception:
    try:
        from backports.zoneinfo import ZoneInfo as _BZI  # pip install backports.zoneinfo (py3.8)
        ZoneInfo = _BZI
    except Exception:
        ZoneInfo = None

try:
    import pytz  # pip install pytz
except Exception:
    pytz = None


def fmt_time(ts: float, tz_name: str) -> str:
    # 1) zoneinfo/backports.zoneinfo
    if ZoneInfo is not None:
        try:
            tz = ZoneInfo(tz_name)
            return datetime.fromtimestamp(ts, tz=tz).isoformat()
        except Exception:
            pass

    # 2) pytz
    if pytz is not None:
        try:
            tz = pytz.timezone(tz_name)
            return datetime.fromtimestamp(ts, tz=tz).isoformat()
        except Exception:
            pass

    # 3) Linux fallback: TZ + tzset
    try:
        old = os.environ.get("TZ")
        os.environ["TZ"] = tz_name
        time.tzset()
        dt = datetime.fromtimestamp(ts).astimezone()
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()
        return dt.isoformat()
    except Exception:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# -----------------------------
# Process helpers
# -----------------------------
def wait_port(host: str, port: int, timeout_s: float) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except Exception:
            time.sleep(0.05)
    return False


def terminate_process_tree(proc: subprocess.Popen, kill_after_s: float = 1.0) -> None:
    if proc.poll() is not None:
        return
    try:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            proc.terminate()
    except Exception:
        pass

    t0 = time.time()
    while time.time() - t0 < kill_after_s:
        if proc.poll() is not None:
            return
        time.sleep(0.05)

    try:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
    except Exception:
        pass


def which(binname: str) -> Optional[str]:
    if os.path.isabs(binname) and os.path.isfile(binname) and os.access(binname, os.X_OK):
        return binname
    if (binname.startswith("./") or "/" in binname) and os.path.isfile(binname) and os.access(binname, os.X_OK):
        return os.path.abspath(binname)
    for p in os.environ.get("PATH", "").split(os.pathsep):
        cand = os.path.join(p, binname)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


# -----------------------------
# Crash detection & signature
# -----------------------------

# Strong crash markers (treat as crash)
CRASH_MARKERS = [
    "ERROR: AddressSanitizer:",
    "SUMMARY: AddressSanitizer:",
    "UndefinedBehaviorSanitizer",
    "runtime error:",
    "Segmentation fault",
    "SIGSEGV",
    "SIGABRT",
    "AddressSanitizer",
    "ABORTING",
    "assertion failed",
    "Assertion `",
    "stack-buffer-overflow",
    "heap-use-after-free",
    "heap-buffer-overflow",
    "global-buffer-overflow",
    "stack-use-after-return",
    "stack-use-after-scope",
    "double-free",
    "alloc-dealloc-mismatch",
]

# Generic "error:" is NOT enough (e.g., live555 RTCPInstance ... error: ... is non-crash),
# so we do not include it.

ASAN_BEGIN_RE = re.compile(r"^==\d+==ERROR:\s+AddressSanitizer:\s+(?P<bug>[\w\-]+)", re.M)
ASAN_SUMMARY_BUG_RE = re.compile(r"^SUMMARY:\s+AddressSanitizer:\s+(?P<bug>[\w\-]+)", re.M)
ASAN_RW_RE = re.compile(r"^(?P<rw>READ|WRITE)\s+of\s+size\s+(?P<size>\d+)", re.M)
ASAN_FRAME_RE = re.compile(
    r"^\s*#(?P<idx>\d+)\s+(?P<addr>0x[0-9a-fA-F]+)?\s*\((?P<bin>.+?)\+0x(?P<off>[0-9a-fA-F]+)\)",
    re.M
)
ASAN_OVERFLOWS_VAR_RE = re.compile(
    r"'\s*(?P<var>[^']+?)'\s*\(line\s+(?P<line>\d+)\)\s*<==\s*Memory access.*overflows this variable",
    re.M
)
ASAN_FRAME_OF_RE = re.compile(
    r"Address .* in frame\s*\n\s*#0\s+0x[0-9a-fA-F]+\s+\((?P<bin>.+?)\+0x(?P<off>[0-9a-fA-F]+)\)",
    re.M
)

FREED_BY_RE = re.compile(r"^freed by thread", re.I | re.M)
ALLOC_BY_RE = re.compile(r"^previously allocated by thread", re.I | re.M)


def has_crash_markers(log_text: str) -> bool:
    lt = log_text.lower()
    for m in CRASH_MARKERS:
        if m.lower() in lt:
            return True
    return False


def _basename_bin(bin_expr: str) -> str:
    b = bin_expr.strip()
    b = b.split()[0]
    return os.path.basename(b)


def _slice_first_asan_block(log_text: str) -> Optional[str]:
    m = ASAN_BEGIN_RE.search(log_text)
    if not m:
        return None
    start = m.start()

    end_m = re.search(r"^==\d+==ABORTING", log_text[start:], re.M)
    if end_m:
        end = start + end_m.end()
        return log_text[start:end]

    # fallback: take first ~400 lines from start
    lines = log_text[start:].splitlines()
    return "\n".join(lines[:400])


def parse_asan_details(log_text: str) -> Optional[Dict]:
    blk = _slice_first_asan_block(log_text)
    if not blk:
        return None

    out: Dict = {}
    m0 = ASAN_BEGIN_RE.search(blk)
    if not m0:
        return None
    out["bug_type"] = m0.group("bug")

    m_rw = ASAN_RW_RE.search(blk)
    if m_rw:
        out["rw"] = m_rw.group("rw")
        out["size"] = int(m_rw.group("size"))
    else:
        out["rw"] = "UNK"
        out["size"] = -1

    frames: List[Tuple[int, str, str]] = []
    for fm in ASAN_FRAME_RE.finditer(blk):
        idx = int(fm.group("idx"))
        bin_base = _basename_bin(fm.group("bin"))
        off = fm.group("off").lower()
        frames.append((idx, bin_base, off))
    frames.sort(key=lambda x: x[0])
    out["frames"] = frames

    if frames:
        out["bin"] = frames[0][1]
        out["pc0_off"] = frames[0][2]
    else:
        out["bin"] = "UNKNOWN_BIN"
        out["pc0_off"] = "unknown"

    # optional pc1
    if len(frames) > 1:
        out["pc1_off"] = frames[1][2]
    else:
        out["pc1_off"] = None

    fm_frame = ASAN_FRAME_OF_RE.search(blk)
    out["frame_off"] = fm_frame.group("off").lower() if fm_frame else None

    mv = ASAN_OVERFLOWS_VAR_RE.search(blk)
    if mv:
        out["overflow_var"] = mv.group("var")
        out["overflow_line"] = int(mv.group("line"))
    else:
        out["overflow_var"] = None
        out["overflow_line"] = None

    def _first_frame_after(marker_re: re.Pattern, text: str) -> Optional[Tuple[str, str]]:
        mm = marker_re.search(text)
        if not mm:
            return None
        sub = text[mm.end():]
        fm = ASAN_FRAME_RE.search(sub)
        if not fm:
            return None
        return (_basename_bin(fm.group("bin")), fm.group("off").lower())

    free0 = _first_frame_after(FREED_BY_RE, blk)
    alloc0 = _first_frame_after(ALLOC_BY_RE, blk)
    out["free0_off"] = free0[1] if free0 else None
    out["alloc0_off"] = alloc0[1] if alloc0 else None

    ms = ASAN_SUMMARY_BUG_RE.search(blk)
    out["summary_bug"] = ms.group("bug") if ms else None

    return out


def build_asan_signature(d: Dict) -> str:
    parts = [
        "ASAN",
        d.get("bug_type", "UNKNOWN"),
        d.get("rw", "UNK"),
        "sz={}".format(d.get("size", -1)),
        "bin={}".format(d.get("bin", "UNKNOWN_BIN")),
        "pc0=0x{}".format(d.get("pc0_off", "unknown")),
    ]

    if d.get("pc1_off"):
        parts.append("pc1=0x{}".format(d["pc1_off"]))

    # stack extra
    if d.get("frame_off"):
        parts.append("frame=0x{}".format(d["frame_off"]))
    if d.get("overflow_var"):
        parts.append("var={}@{}".format(d["overflow_var"], d.get("overflow_line", -1)))

    # heap uaf extra
    if d.get("free0_off"):
        parts.append("free0=0x{}".format(d["free0_off"]))
    if d.get("alloc0_off"):
        parts.append("alloc0=0x{}".format(d["alloc0_off"]))

    return "|".join(parts)


def extract_signature(log_text: str) -> str:
    # Prefer ASAN structured signature
    d = parse_asan_details(log_text)
    if d:
        return build_asan_signature(d)

    # Fallback: UBSAN line if present
    m = re.search(r"runtime error:\s+(.+)", log_text, re.IGNORECASE)
    if m:
        return "UBSAN|{}".format(m.group(1).strip())

    # Fallback: first strong crash marker line(s)
    lines = log_text.splitlines()
    for i, line in enumerate(lines):
        if any(mk.lower() in line.lower() for mk in CRASH_MARKERS):
            ctx = [line.strip()]
            for j in range(i + 1, min(i + 6, len(lines))):
                if lines[j].strip():
                    ctx.append(lines[j].strip())
                if len(ctx) >= 3:
                    break
            return "FATAL|" + " | ".join(ctx)

    return "NO_SIG"


# -----------------------------
# Data structures
# -----------------------------
@dataclass
class SeedResult:
    seed_path: str
    seed_mtime: float
    reproduced: bool
    server_returncode: Optional[int]
    killed_by_us: bool
    signature: str
    signature_hash: str
    server_log_path: str
    replay_log_path: str


@dataclass
class UniqueCrash:
    signature: str
    signature_hash: str
    first_seen_ts: float
    first_seen_seed: str
    count: int


# -----------------------------
# Main
# -----------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--subdir", default="replayable-crashes")
    ap.add_argument("--proto", required=True)
    ap.add_argument("--port", type=int, default=8554)
    ap.add_argument("--host", default="127.0.0.1")

    ap.add_argument("--server-cmd", default="./testProgs/testOnDemandRTSPServer 8554")
    ap.add_argument("--replay-bin", default="aflnet-replay")

    ap.add_argument("--server-start-timeout", type=float, default=2.0)
    ap.add_argument("--replay-timeout", type=float, default=5.0)
    ap.add_argument("--server-grace", type=float, default=1.0)

    ap.add_argument("--tz", default="America/Los_Angeles")

    ap.add_argument("--keep-nonrepro", action="store_true")

    ap.add_argument("--seed-regex", default=r"^id:", help="Only include seeds whose basename matches this regex (default: ^id:)")
    ap.add_argument("--include-readme", action="store_true", help="Include README.txt (default: false)")

    args = ap.parse_args()

    seed_dir = os.path.join(args.out_dir, args.subdir)
    if not os.path.isdir(seed_dir):
        print("[!] Seed dir not found: {}".format(seed_dir), file=sys.stderr)
        sys.exit(2)

    seed_pat = re.compile(args.seed_regex)

    # Collect seeds
    seeds: List[Tuple[float, str]] = []
    for root, _, files in os.walk(seed_dir):
        for fn in files:
            if not args.include_readme and fn == "README.txt":
                continue
            if not seed_pat.search(fn):
                continue
            path = os.path.join(root, fn)
            if os.path.isfile(path):
                try:
                    st = os.stat(path)
                    seeds.append((st.st_mtime, path))
                except Exception:
                    continue

    if not seeds:
        print("[!] No seed files matched under: {}".format(seed_dir), file=sys.stderr)
        print("    Try: --seed-regex '.*' to include all files.", file=sys.stderr)
        sys.exit(1)

    seeds.sort(key=lambda x: x[0])

    out_base = os.path.join(args.out_dir, "crash_first_seen")
    logs_dir = os.path.join(out_base, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    server_cmd_argv = shlex.split(args.server_cmd)

    rb = which(args.replay_bin)
    if rb is None:
        print("[!] aflnet-replay not found/executable: {}".format(args.replay_bin), file=sys.stderr)
        sys.exit(2)

    results: List[SeedResult] = []

    for idx, (mtime, seed_path) in enumerate(seeds, 1):
        seed_base = os.path.basename(seed_path)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", seed_base)
        server_log_path = os.path.join(logs_dir, "{:05d}_{}.server.log".format(idx, safe_name))
        replay_log_path = os.path.join(logs_dir, "{:05d}_{}.replay.log".format(idx, safe_name))

        killed_by_us = False

        # Start server
        try:
            srv_log = open(server_log_path, "wb")
            srv_proc = subprocess.Popen(
                server_cmd_argv,
                stdout=srv_log,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                env=os.environ.copy(),
            )
        except Exception as e:
            print("[!] Failed to start server for seed {}: {}".format(seed_path, e), file=sys.stderr)
            try:
                srv_log.close()
            except Exception:
                pass
            continue

        ready = wait_port(args.host, args.port, args.server_start_timeout)

        # Replay
        replay_argv = [rb, seed_path, args.proto, str(args.port), "1"]
        try:
            with open(replay_log_path, "wb") as rep_log:
                rep_log.write(("CMD: " + " ".join(replay_argv) + "\n").encode("utf-8", "ignore"))
                if not ready:
                    rep_log.write(b"[WARN] server port not ready before replay\n")
                rep_log.flush()

                try:
                    subprocess.run(
                        replay_argv,
                        stdout=rep_log,
                        stderr=subprocess.STDOUT,
                        timeout=args.replay_timeout,
                        env=os.environ.copy(),
                    )
                except subprocess.TimeoutExpired:
                    rep_log.write(b"[TIMEOUT] replay timeout, killed\n")
        except Exception:
            pass

        # Allow crash to surface
        time.sleep(args.server_grace)

        # If server exited by itself, poll will be not None
        srv_rc = srv_proc.poll()

        # If still alive, we terminate it; this should not be counted as crash
        if srv_rc is None:
            killed_by_us = True
            terminate_process_tree(srv_proc, kill_after_s=1.0)
            srv_rc = srv_proc.poll()

        try:
            srv_log.close()
        except Exception:
            pass

        # Read server log
        try:
            with open(server_log_path, "rb") as f:
                server_log_text = f.read().decode("utf-8", "replace")
        except Exception:
            server_log_text = ""

        # Decide crash:
        #   - crash markers in log => crash
        #   - OR server died by itself abnormally (not killed_by_us and returncode != 0) => crash
        reproduced = False
        if has_crash_markers(server_log_text):
            reproduced = True
        elif (not killed_by_us) and (srv_rc is not None) and (srv_rc != 0):
            reproduced = True

        sig = extract_signature(server_log_text) if reproduced else "NO_CRASH"
        sig_hash = hashlib.sha1(sig.encode("utf-8", "ignore")).hexdigest()[:12]

        if reproduced or args.keep_nonrepro:
            results.append(SeedResult(
                seed_path=seed_path,
                seed_mtime=mtime,
                reproduced=reproduced,
                server_returncode=srv_rc,
                killed_by_us=killed_by_us,
                signature=sig,
                signature_hash=sig_hash,
                server_log_path=server_log_path,
                replay_log_path=replay_log_path,
            ))

        if idx % 20 == 0 or idx == len(seeds):
            print("[*] {}/{} processed. last: reproduced={} killed_by_us={} sig={}".format(
                idx, len(seeds), reproduced, killed_by_us, sig_hash
            ))

    # Aggregate unique crashes
    uniq: Dict[str, UniqueCrash] = {}
    for r in results:
        if not r.reproduced:
            continue
        h = r.signature_hash
        if h not in uniq:
            uniq[h] = UniqueCrash(
                signature=r.signature,
                signature_hash=h,
                first_seen_ts=r.seed_mtime,
                first_seen_seed=r.seed_path,
                count=1,
            )
        else:
            uc = uniq[h]
            uc.count += 1
            if r.seed_mtime < uc.first_seen_ts:
                uc.first_seen_ts = r.seed_mtime
                uc.first_seen_seed = r.seed_path

    uniq_list = sorted(uniq.values(), key=lambda x: x.first_seen_ts)

    os.makedirs(out_base, exist_ok=True)
    report_txt = os.path.join(out_base, "report.txt")
    report_csv = os.path.join(out_base, "report.csv")
    report_json = os.path.join(out_base, "report.json")

    with open(report_txt, "w", encoding="utf-8") as f:
        f.write("OUT_DIR: {}\n".format(args.out_dir))
        f.write("SEED_DIR: {}\n".format(seed_dir))
        f.write("PROTO: {}\n".format(args.proto))
        f.write("SERVER_CMD: {}\n".format(args.server_cmd))
        f.write("REPLAY_BIN: {}\n".format(rb))
        f.write("PORT: {}\n".format(args.port))
        f.write("TIMEZONE: {}\n".format(args.tz))
        f.write("SEED_REGEX: {}\n".format(args.seed_regex))
        f.write("\n=== UNIQUE CRASHES (first-seen by seed mtime) ===\n\n")
        if not uniq_list:
            f.write("No reproduced crashes found.\n")
        for i, uc in enumerate(uniq_list, 1):
            f.write("[{}] crash_id={}\n".format(i, uc.signature_hash))
            f.write("    first_seen={}\n".format(fmt_time(uc.first_seen_ts, args.tz)))
            f.write("    first_seed={}\n".format(uc.first_seen_seed))
            f.write("    count={}\n".format(uc.count))
            f.write("    signature:\n")
            for line in uc.signature.splitlines():
                f.write("      {}\n".format(line))
            f.write("\n")

    with open(report_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["crash_id", "first_seen", "count", "first_seed", "signature"])
        for uc in uniq_list:
            w.writerow([
                uc.signature_hash,
                fmt_time(uc.first_seen_ts, args.tz),
                uc.count,
                uc.first_seen_seed,
                uc.signature.replace("\n", "\\n"),
            ])

    unique_json = []
    for u in uniq_list:
        d = dataclasses.asdict(u)
        d["first_seen"] = fmt_time(u.first_seen_ts, args.tz)
        unique_json.append(d)

    per_seed_json = []
    for r in results:
        d = dataclasses.asdict(r)
        d["seed_mtime_iso"] = fmt_time(r.seed_mtime, args.tz)
        per_seed_json.append(d)

    with open(report_json, "w", encoding="utf-8") as f:
        obj = {
            "meta": {
                "out_dir": args.out_dir,
                "seed_dir": seed_dir,
                "proto": args.proto,
                "port": args.port,
                "server_cmd": args.server_cmd,
                "replay_bin": rb,
                "timezone": args.tz,
                "seed_regex": args.seed_regex,
                "total_seeds_matched": len(seeds),
                "total_results_kept": len(results),
                "unique_crashes": len(uniq_list),
            },
            "unique": unique_json,
            "per_seed": per_seed_json,
        }
        json.dump(obj, f, ensure_ascii=False, indent=2)

    print("\n[+] Done.")
    print("    Report txt : {}".format(report_txt))
    print("    Report csv : {}".format(report_csv))
    print("    Report json: {}".format(report_json))
    print("    Logs dir   : {}".format(logs_dir))


if __name__ == "__main__":
    main()
