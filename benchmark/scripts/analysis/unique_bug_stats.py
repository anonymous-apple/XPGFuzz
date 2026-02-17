#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
unique_bug_stats.py

Aggregate unique crash info across all replications for a subject.
Reads crash_first_seen/report.json from each out-*.tar.gz in results-<subject>.

Outputs:
  - unique_bugs_per_run.csv
  - unique_bugs_summary.csv
  - unique_bugs_summary.json
  - unique_bugs_missing.txt

Usage:
  python3 unique_bug_stats.py --results-dir results-live555 --subject live555
"""

import argparse
import csv
import json
import os
import re
import statistics
import tarfile
from typing import Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True, help="Path to results-<subject> directory")
    ap.add_argument("--subject", required=True, help="Subject name used in out-<subject>-<fuzzer>_<rep>.tar.gz")
    ap.add_argument("--out-prefix", default="unique_bugs", help="Output file prefix (default: unique_bugs)")
    return ap.parse_args()


def extract_report_json(tar_path: str) -> Optional[Dict]:
    try:
        with tarfile.open(tar_path, "r:gz") as tf:
            # find report.json inside crash_first_seen
            for member in tf.getmembers():
                if member.isfile() and member.name.endswith("/crash_first_seen/report.json"):
                    f = tf.extractfile(member)
                    if not f:
                        return None
                    data = f.read().decode("utf-8", "replace")
                    return json.loads(data)
    except Exception:
        return None
    return None


def parse_fuzzer_rep(filename: str, subject: str) -> Optional[Tuple[str, int]]:
    # Expect out-<subject>-<fuzzer>_<rep>.tar.gz
    # Use subject to strip prefix, then parse rep.
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


def main() -> None:
    args = parse_args()
    results_dir = args.results_dir
    subject = args.subject
    out_prefix = args.out_prefix

    if not os.path.isdir(results_dir):
        raise SystemExit(f"[!] results dir not found: {results_dir}")

    tar_files = [
        os.path.join(results_dir, f)
        for f in os.listdir(results_dir)
        if f.endswith(".tar.gz") and f.startswith(f"out-{subject}-")
    ]

    per_run_rows = []
    missing = []
    by_fuzzer: Dict[str, List[Dict]] = {}
    union_ids: Dict[str, set] = {}

    for tar_path in sorted(tar_files):
        parsed = parse_fuzzer_rep(os.path.basename(tar_path), subject)
        if not parsed:
            continue
        fuzzer, rep = parsed

        report = extract_report_json(tar_path)
        if not report:
            missing.append(os.path.basename(tar_path))
            continue

        meta = report.get("meta", {})
        unique_list = report.get("unique", [])
        unique_count = meta.get("unique_crashes", len(unique_list))
        total_seeds = meta.get("total_seeds_matched", "")

        crash_ids = set()
        for u in unique_list:
            cid = u.get("signature_hash") or u.get("signature")
            if cid:
                crash_ids.add(str(cid))

        per_run_rows.append({
            "subject": subject,
            "fuzzer": fuzzer,
            "rep": rep,
            "unique_crashes": unique_count,
            "total_seeds_matched": total_seeds,
            "tar": os.path.basename(tar_path),
        })

        by_fuzzer.setdefault(fuzzer, []).append({
            "rep": rep,
            "unique_crashes": unique_count,
            "tar": os.path.basename(tar_path),
        })
        union_ids.setdefault(fuzzer, set()).update(crash_ids)

    # Write per-run CSV
    per_run_csv = os.path.join(results_dir, f"{out_prefix}_per_run.csv")
    with open(per_run_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["subject", "fuzzer", "rep", "unique_crashes", "total_seeds_matched", "tar"])
        for r in sorted(per_run_rows, key=lambda x: (x["fuzzer"], x["rep"])):
            w.writerow([r["subject"], r["fuzzer"], r["rep"], r["unique_crashes"], r["total_seeds_matched"], r["tar"]])

    # Write summary CSV/JSON
    summary_rows = []
    summary_json = {
        "subject": subject,
        "per_fuzzer": {},
    }

    for fuzzer, rows in sorted(by_fuzzer.items(), key=lambda x: x[0]):
        counts = [r["unique_crashes"] for r in rows]
        counts_sorted = sorted(counts)
        summary = {
            "fuzzer": fuzzer,
            "reps_with_data": len(counts),
            "unique_min": min(counts) if counts else 0,
            "unique_max": max(counts) if counts else 0,
            "unique_mean": round(statistics.mean(counts), 3) if counts else 0,
            "unique_median": round(statistics.median(counts), 3) if counts else 0,
            "unique_union_across_reps": len(union_ids.get(fuzzer, set())),
        }
        summary_rows.append(summary)
        summary_json["per_fuzzer"][fuzzer] = summary

    summary_csv = os.path.join(results_dir, f"{out_prefix}_summary.csv")
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "fuzzer", "reps_with_data", "unique_min", "unique_mean",
            "unique_median", "unique_max", "unique_union_across_reps"
        ])
        for s in summary_rows:
            w.writerow([
                s["fuzzer"], s["reps_with_data"], s["unique_min"], s["unique_mean"],
                s["unique_median"], s["unique_max"], s["unique_union_across_reps"]
            ])

    summary_json_path = os.path.join(results_dir, f"{out_prefix}_summary.json")
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, ensure_ascii=False, indent=2)

    # Missing reports
    missing_path = os.path.join(results_dir, f"{out_prefix}_missing.txt")
    with open(missing_path, "w", encoding="utf-8") as f:
        if missing:
            f.write("\n".join(missing) + "\n")

    print("[+] Unique bug stats written:")
    print(f"  - {per_run_csv}")
    print(f"  - {summary_csv}")
    print(f"  - {summary_json_path}")
    if missing:
        print(f"[!] Missing report.json in {len(missing)} tarballs (see {missing_path})")


if __name__ == "__main__":
    main()
