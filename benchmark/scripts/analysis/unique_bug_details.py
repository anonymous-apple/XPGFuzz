#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
unique_bug_details.py

Extract detailed bug artifacts per fuzzer/replication:
  - message sequence (seed file)
  - server/replay logs
  - crash signature, first_seen, seed time

Reads crash_first_seen/report.json from each out-*.tar.gz in results-<subject>.
Extracts referenced artifacts into results-<subject>/unique_bug_details/.

Outputs:
  - unique_bug_details.csv
  - unique_bug_details.json

Usage:
  python3 unique_bug_details.py --results-dir results-live555 --subject live555
"""

import argparse
import csv
import json
import os
import re
import tarfile
from typing import Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True, help="Path to results-<subject> directory")
    ap.add_argument("--subject", required=True, help="Subject name used in out-<subject>-<fuzzer>_<rep>.tar.gz")
    ap.add_argument("--out-dir", default=None, help="Output directory (default: results-<subject>/unique_bug_details)")
    return ap.parse_args()


def parse_fuzzer_rep(filename: str, subject: str) -> Optional[Tuple[str, int]]:
    base = os.path.basename(filename)
    prefix = f"out-{subject}-"
    if not base.startswith(prefix) or not base.endswith(".tar.gz"):
        return None
    mid = base[len(prefix):]
    m = re.match(r"(.+)_([0-9]+)\.tar\.gz$", mid)
    if not m:
        return None
    fuzzer = m.group(1)
    rep = int(m.group(2))
    return fuzzer, rep


def read_report_json(tf: tarfile.TarFile) -> Optional[Dict]:
    for member in tf.getmembers():
        if member.isfile() and member.name.endswith("/crash_first_seen/report.json"):
            f = tf.extractfile(member)
            if not f:
                return None
            data = f.read().decode("utf-8", "replace")
            return json.loads(data)
    return None


def find_member_by_basename(tf: tarfile.TarFile, suffix: str) -> Optional[tarfile.TarInfo]:
    for member in tf.getmembers():
        if member.isfile() and member.name.endswith(suffix):
            return member
    return None


def extract_member(tf: tarfile.TarFile, member: tarfile.TarInfo, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    f = tf.extractfile(member)
    if not f:
        return
    with open(out_path, "wb") as out_f:
        out_f.write(f.read())


def main() -> None:
    args = parse_args()
    results_dir = args.results_dir
    subject = args.subject
    out_dir = args.out_dir or os.path.join(results_dir, "unique_bug_details")

    if not os.path.isdir(results_dir):
        raise SystemExit(f"[!] results dir not found: {results_dir}")

    tar_files = [
        os.path.join(results_dir, f)
        for f in os.listdir(results_dir)
        if f.endswith(".tar.gz") and f.startswith(f"out-{subject}-")
    ]

    rows = []
    details = []
    os.makedirs(out_dir, exist_ok=True)

    for tar_path in sorted(tar_files):
        parsed = parse_fuzzer_rep(os.path.basename(tar_path), subject)
        if not parsed:
            continue
        fuzzer, rep = parsed

        with tarfile.open(tar_path, "r:gz") as tf:
            report = read_report_json(tf)
            if not report:
                continue

            unique_list = report.get("unique", [])
            per_seed = report.get("per_seed", [])

            # Map signature_hash -> signature
            sig_map = {}
            for u in unique_list:
                if "signature_hash" in u:
                    sig_map[u["signature_hash"]] = u.get("signature", "")

            for r in per_seed:
                if not r.get("reproduced", False):
                    continue
                sig_hash = r.get("signature_hash", "")
                signature = r.get("signature", "") or sig_map.get(sig_hash, "")

                seed_path = r.get("seed_path", "")
                seed_base = os.path.basename(seed_path) if seed_path else ""
                server_log = r.get("server_log_path", "")
                replay_log = r.get("replay_log_path", "")
                server_log_base = os.path.basename(server_log) if server_log else ""
                replay_log_base = os.path.basename(replay_log) if replay_log else ""

                # extract seed
                seed_member = None
                if seed_base:
                    seed_member = find_member_by_basename(tf, f"/replayable-crashes/{seed_base}")
                    if not seed_member:
                        seed_member = find_member_by_basename(tf, f"/crashes/{seed_base}")

                # extract logs
                server_member = find_member_by_basename(tf, f"/crash_first_seen/logs/{server_log_base}") if server_log_base else None
                replay_member = find_member_by_basename(tf, f"/crash_first_seen/logs/{replay_log_base}") if replay_log_base else None

                # output paths
                crash_id = sig_hash or "unknown"
                base_dir = os.path.join(out_dir, fuzzer, f"rep_{rep}", crash_id, seed_base or "seed")
                os.makedirs(base_dir, exist_ok=True)

                seed_out = os.path.join(base_dir, seed_base) if seed_member else ""
                server_out = os.path.join(base_dir, server_log_base) if server_member else ""
                replay_out = os.path.join(base_dir, replay_log_base) if replay_member else ""

                if seed_member and seed_out:
                    extract_member(tf, seed_member, seed_out)
                if server_member and server_out:
                    extract_member(tf, server_member, server_out)
                if replay_member and replay_out:
                    extract_member(tf, replay_member, replay_out)

                row = {
                    "subject": subject,
                    "fuzzer": fuzzer,
                    "rep": rep,
                    "crash_id": crash_id,
                    "signature": signature,
                    "seed_mtime_iso": r.get("seed_mtime_iso", ""),
                    "seed_file": seed_out,
                    "server_log": server_out,
                    "replay_log": replay_out,
                    "server_returncode": r.get("server_returncode", ""),
                    "killed_by_us": r.get("killed_by_us", ""),
                }
                rows.append(row)
                details.append(row)

    # Write CSV/JSON
    csv_path = os.path.join(results_dir, "unique_bug_details.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "subject", "fuzzer", "rep", "crash_id", "seed_mtime_iso",
            "seed_file", "server_log", "replay_log", "server_returncode",
            "killed_by_us", "signature"
        ])
        for r in rows:
            w.writerow([
                r["subject"], r["fuzzer"], r["rep"], r["crash_id"], r["seed_mtime_iso"],
                r["seed_file"], r["server_log"], r["replay_log"], r["server_returncode"],
                r["killed_by_us"], r["signature"].replace("\n", "\\n")
            ])

    json_path = os.path.join(results_dir, "unique_bug_details.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(details, f, ensure_ascii=False, indent=2)

    print("[+] Unique bug details written:")
    print(f"  - {csv_path}")
    print(f"  - {json_path}")
    print(f"  - artifacts: {out_dir}")


if __name__ == "__main__":
    main()
