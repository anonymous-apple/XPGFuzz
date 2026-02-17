#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
crash_timing.py

Parse:
  1) out-dir/fuzzer_stats for start_time epoch seconds
  2) out-dir/crash_first_seen/report.txt for unique crash first_seen timestamps

Output:
  - CSV/JSON with: crash_id, crash_type, stack_info, first_seen, seconds_since_start, human_since_start, first_seed, count

Usage:
  python3 crash_timing.py --out-dir /path/to/out-dir

Optional:
  --fuzzer-stats /path/to/fuzzer_stats
  --report /path/to/report.txt
  --csv /path/to/output.csv
  --json /path/to/output.json
"""

import argparse
import csv
import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional, Dict


START_TIME_RE = re.compile(r"^start_time\s*:\s*(\d+)\s*$")
CRASH_HEADER_RE = re.compile(r"^\[\d+\]\s+crash_id=([0-9a-fA-F]+)\s*$")
FIRST_SEEN_RE = re.compile(r"^\s*first_seen=(.+)\s*$")
FIRST_SEED_RE = re.compile(r"^\s*first_seed=(.+)\s*$")
COUNT_RE = re.compile(r"^\s*count=(\d+)\s*$")


@dataclass
class CrashRow:
    crash_id: str
    crash_type: str
    stack_info: str
    first_seen: str
    seconds_since_start: int
    human_since_start: str
    first_seed: str
    count: int


def parse_start_time(fuzzer_stats_path: str) -> int:
    with open(fuzzer_stats_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = START_TIME_RE.match(line.strip())
            if m:
                return int(m.group(1))
    raise RuntimeError(f"Cannot find 'start_time' in {fuzzer_stats_path}")


def iso_to_epoch_seconds(iso_str: str) -> int:
    s = iso_str.strip()
    # handle 'Z'
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # datetime.fromisoformat supports offsets like -08:00, +00:00
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        # if timezone missing, assume UTC (safer than local)
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def format_duration(seconds: int) -> str:
    neg = seconds < 0
    s = abs(seconds)
    days = s // 86400
    s %= 86400
    hours = s // 3600
    s %= 3600
    minutes = s // 60
    secs = s % 60
    if days > 0:
        out = f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        out = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"-{out}" if neg else out


def summarize_stack_from_signature(signature_text: str) -> str:
    """
    Prefer compact stack info for ASAN signature in the form:
      ASAN|<type>|...|pc0=0x...|pc1=0x...|free0=0x...|alloc0=0x...|var=...@...|frame=0x...
    Otherwise return the raw signature text (trimmed).
    """
    sig = signature_text.strip()

    if sig.startswith("ASAN|"):
        parts = sig.split("|")
        crash_type = parts[1] if len(parts) > 1 else "ASAN"
        kv = []
        # keep these keys if exist
        for p in parts:
            if p.startswith("bin=") or p.startswith("pc0=") or p.startswith("pc1=") or p.startswith("free0=") or p.startswith("alloc0=") or p.startswith("var=") or p.startswith("frame="):
                kv.append(p)
        if kv:
            return f"{crash_type} " + " ".join(kv)
        return sig

    if sig.startswith("UBSAN|"):
        return sig  # already short

    # If old-style report contains "ASAN_SUMMARY:" etc., keep first line
    lines = [x.rstrip() for x in sig.splitlines() if x.strip()]
    if not lines:
        return "EMPTY_SIGNATURE"
    # keep up to 6 lines to avoid exploding CSV; full content still in json
    if len(lines) <= 6:
        return "\n".join(lines)
    return "\n".join(lines[:6]) + "\n... (truncated)"


def infer_crash_type(signature_text: str) -> str:
    sig = signature_text.strip()
    if sig.startswith("ASAN|"):
        parts = sig.split("|")
        return parts[1] if len(parts) > 1 else "ASAN"
    if sig.startswith("UBSAN|"):
        return "UBSAN"
    # best-effort for other formats
    low = sig.lower()
    for k in [
        "heap-use-after-free",
        "stack-buffer-overflow",
        "heap-buffer-overflow",
        "global-buffer-overflow",
        "stack-use-after-return",
        "stack-use-after-scope",
        "double-free",
        "alloc-dealloc-mismatch",
        "segv",
        "sigsegv",
        "sigabrt",
    ]:
        if k in low:
            return k.upper() if k.startswith("sig") or k == "segv" else k
    return "FATAL_OR_UNKNOWN"


def parse_report(report_path: str) -> List[Dict]:
    """
    Parse report.txt produced by first_seen_crash.py.
    Return list of dict with keys: crash_id, first_seen, first_seed, count, signature_text
    """
    with open(report_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    crashes = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        mh = CRASH_HEADER_RE.match(line.strip())
        if not mh:
            i += 1
            continue

        crash_id = mh.group(1)
        first_seen = ""
        first_seed = ""
        count = 0
        signature_lines: List[str] = []

        i += 1
        in_signature = False

        while i < len(lines):
            cur = lines[i].rstrip("\n")

            # next crash starts
            if CRASH_HEADER_RE.match(cur.strip()):
                break

            if cur.strip() == "signature:":
                in_signature = True
                i += 1
                continue

            if in_signature:
                # signature lines are usually indented; keep raw but strip leading spaces for readability
                if cur.strip() == "":
                    # blank line ends this crash block (often)
                    # but we can keep reading until next header; break here to be safe
                    pass
                signature_lines.append(cur.strip())
                i += 1
                continue

            mfs = FIRST_SEEN_RE.match(cur)
            if mfs:
                first_seen = mfs.group(1).strip()
                i += 1
                continue

            mseed = FIRST_SEED_RE.match(cur)
            if mseed:
                first_seed = mseed.group(1).strip()
                i += 1
                continue

            mc = COUNT_RE.match(cur)
            if mc:
                count = int(mc.group(1))
                i += 1
                continue

            i += 1

        crashes.append({
            "crash_id": crash_id,
            "first_seen": first_seen,
            "first_seed": first_seed,
            "count": count,
            "signature_text": "\n".join([x for x in signature_lines if x != ""]),
        })

    return crashes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--fuzzer-stats", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    out_dir = args.out_dir
    fuzzer_stats_path = args.fuzzer_stats or os.path.join(out_dir, "fuzzer_stats")
    report_path = args.report or os.path.join(out_dir, "crash_first_seen", "report.txt")

    if not os.path.isfile(fuzzer_stats_path):
        raise SystemExit(f"[!] fuzzer_stats not found: {fuzzer_stats_path}")
    if not os.path.isfile(report_path):
        raise SystemExit(f"[!] report.txt not found: {report_path}")

    start_time = parse_start_time(fuzzer_stats_path)

    crashes = parse_report(report_path)
    rows: List[CrashRow] = []

    for c in crashes:
        crash_id = c["crash_id"]
        first_seen = c["first_seen"]
        if not first_seen:
            # if missing, skip
            continue
        first_seen_epoch = iso_to_epoch_seconds(first_seen)
        delta = int(first_seen_epoch - start_time)

        sig_text = c["signature_text"] or ""
        crash_type = infer_crash_type(sig_text)
        stack_info = summarize_stack_from_signature(sig_text)

        rows.append(CrashRow(
            crash_id=crash_id,
            crash_type=crash_type,
            stack_info=stack_info,
            first_seen=first_seen,
            seconds_since_start=delta,
            human_since_start=format_duration(delta),
            first_seed=c.get("first_seed", ""),
            count=int(c.get("count", 0) or 0),
        ))

    # sort by time found
    rows.sort(key=lambda r: r.seconds_since_start)

    out_base = os.path.join(out_dir, "crash_first_seen")
    os.makedirs(out_base, exist_ok=True)

    csv_path = args.csv or os.path.join(out_base, "crash_timing.csv")
    json_path = args.json or os.path.join(out_base, "crash_timing.json")

    # write CSV (stack_info may contain newlines; we replace with \n)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "crash_id", "crash_type", "first_seen",
            "seconds_since_start", "human_since_start",
            "count", "first_seed", "stack_info"
        ])
        for r in rows:
            w.writerow([
                r.crash_id, r.crash_type, r.first_seen,
                r.seconds_since_start, r.human_since_start,
                r.count, r.first_seed,
                r.stack_info.replace("\n", "\\n")
            ])

    # write JSON (keep full stack_info)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in rows], f, ensure_ascii=False, indent=2)

    # print to stdout (readable)
    print(f"OUT_DIR: {out_dir}")
    print(f"start_time(epoch): {start_time}")
    print(f"report: {report_path}")
    print(f"written: {csv_path}")
    print(f"written: {json_path}")
    print("\n=== Crash timing (sorted by time_to_find) ===\n")
    for r in rows:
        print(f"- crash_id={r.crash_id}  type={r.crash_type}  time_to_find={r.human_since_start} ({r.seconds_since_start}s)")
        # print a compact stack line (first line only)
        first_line = r.stack_info.splitlines()[0] if r.stack_info else ""
        if len(first_line) > 200:
            first_line = first_line[:200] + "..."
        print(f"  stack: {first_line}")
        print(f"  first_seen: {r.first_seen}")
        print(f"  first_seed: {r.first_seed}")
        print(f"  count: {r.count}\n")


if __name__ == "__main__":
    main()
