#!/usr/bin/env python3
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

METRICS = (
    ("line_cov_%", "results.csv", "cov_type", "l_per", "cov", True),
    ("branch_cov_%", "results.csv", "cov_type", "b_per", "cov", True),
    ("states", "states.csv", "state_type", "nodes", "state", True),
    ("transitions", "states.csv", "state_type", "edges", "state", True),
)


def final_per_run(df, type_col, type_val, val_col):
    d = df[df[type_col] == type_val].sort_values("time")
    return d.groupby(["fuzzer", "run"], as_index=False).tail(1)[["fuzzer", "run", "time", val_col]]


def time_limit_min(df, fuzzer, run, type_col, type_val):
    d = df[(df["fuzzer"] == fuzzer) & (df["run"] == run) & (df[type_col] == type_val)].sort_values("time")
    if d.empty:
        return np.nan
    return float((d["time"].iloc[-1] - d["time"].iloc[0]) / 60.0)


def reach_time_min(df, fuzzer, run, type_col, type_val, val_col, target):
    d = df[(df["fuzzer"] == fuzzer) & (df["run"] == run) & (df[type_col] == type_val)].sort_values("time")
    if d.empty:
        return np.nan
    t0 = d["time"].iloc[0]
    hit = d[d[val_col] >= target]
    if hit.empty:
        return np.nan
    return float((hit["time"].iloc[0] - t0) / 60.0)


def main():
    ap = argparse.ArgumentParser(description="Compute XPGFuzz speed-up vs AFLNet/chatafl (paper-style).")
    ap.add_argument("--bench", default=str(Path(__file__).resolve().parent), help="benchmark dir")
    ap.add_argument("--protocols", default="", help="comma-separated protocol codes; default auto-detect")
    args = ap.parse_args()

    bench = Path(args.bench)
    if args.protocols:
        result_dirs = [bench / f"results-{p.strip()}" for p in args.protocols.split(",") if p.strip()]
    else:
        result_dirs = sorted(
            d for d in bench.glob("results-*") if d.is_dir() and "old" not in d.name and "replay" not in d.name
        )

    rows = []
    for rd in result_dirs:
        proto = rd.name[len("results-") :]
        for metric, fname, type_col, type_val, val_col, bigger_is_better in METRICS:
            f = rd / fname
            if not f.exists():
                continue
            df = pd.read_csv(f)
            if bigger_is_better:
                pass
            else:
                df[val_col] = -df[val_col]

            # Targets: baseline final (per run), averaged
            finals = final_per_run(df, type_col, type_val, val_col)
            for baseline in ("aflnet", "chatafl"):
                base = finals[finals["fuzzer"] == baseline]
                xpg = finals[finals["fuzzer"] == "xpgfuzz"]
                if base.empty or xpg.empty:
                    rows.append(dict(protocol=proto, metric=metric, baseline=baseline, speedup=np.nan))
                    continue

                target = float(base[val_col].mean())
                # baseline budget: mean runtime (minutes)
                base_limits = [
                    time_limit_min(df, baseline, int(r), type_col, type_val) for r in base["run"].unique()
                ]
                budget = float(np.nanmean(base_limits)) if np.isfinite(base_limits).any() else np.nan

                reach_times = [
                    reach_time_min(df, "xpgfuzz", int(r), type_col, type_val, val_col, target)
                    for r in xpg["run"].unique()
                ]
                t_reach = float(np.nanmean(reach_times)) if np.isfinite(reach_times).any() else np.nan
                speed = (budget / t_reach) if (np.isfinite(budget) and np.isfinite(t_reach) and t_reach > 0) else np.nan
                rows.append(dict(protocol=proto, metric=metric, baseline=baseline, speedup=speed))

    out = pd.DataFrame(rows)
    wide = out.pivot_table(index="protocol", columns=["metric", "baseline"], values="speedup", aggfunc="first")
    wide.columns = [f"Speedup_{m}_xpgfuzz_vs_{b}" for (m, b) in wide.columns]
    wide = wide.reset_index().sort_values("protocol")
    print(wide.to_csv(index=False))


if __name__ == "__main__":
    main()

