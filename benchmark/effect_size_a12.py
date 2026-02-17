#!/usr/bin/env python3
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

FUZZERS = ("aflnet", "chatafl", "xpgfuzz")
PAIRS = (("xpgfuzz", "aflnet"), ("xpgfuzz", "chatafl"))
METRICS = (
    ("line_cov_%", "results.csv", "cov_type", "l_per", "cov"),
    ("branch_cov_%", "results.csv", "cov_type", "b_per", "cov"),
    ("states", "states.csv", "state_type", "nodes", "state"),
    ("transitions", "states.csv", "state_type", "edges", "state"),
)


def a12(x, y):
    x, y = np.asarray(list(x)), np.asarray(list(y))
    if x.size == 0 or y.size == 0:
        return np.nan
    gt = (x[:, None] > y[None, :]).sum()
    eq = (x[:, None] == y[None, :]).sum()
    return float((gt + 0.5 * eq) / (x.size * y.size))


def final_per_run(df, type_col, type_val, val_col):
    d = df[df[type_col] == type_val].sort_values("time")
    return d.groupby(["fuzzer", "run"], as_index=False).tail(1)[["fuzzer", "run", val_col]]


def main():
    ap = argparse.ArgumentParser(description="Compute A12 (Vargha-Delaney) effect sizes per protocol.")
    ap.add_argument("--bench", default=str(Path(__file__).resolve().parent), help="benchmark dir")
    ap.add_argument("--protocols", default="", help="comma-separated protocol codes; default auto-detect")
    ap.add_argument("--format", choices=("paper", "long"), default="paper", help="output shape")
    args = ap.parse_args()

    bench = Path(args.bench)
    if args.protocols:
        protos = [p.strip() for p in args.protocols.split(",") if p.strip()]
        result_dirs = [bench / f"results-{p}" for p in protos]
    else:
        result_dirs = sorted(
            d for d in bench.glob("results-*") if d.is_dir() and "old" not in d.name and "replay" not in d.name
        )

    rows = []
    for rd in result_dirs:
        proto = rd.name[len("results-") :]
        for metric, fname, type_col, type_val, val_col in METRICS:
            f = rd / fname
            if not f.exists():
                continue
            df = pd.read_csv(f)
            df = df[df["fuzzer"].isin(FUZZERS)]
            finals = final_per_run(df, type_col, type_val, val_col)

            vals = {fz: finals[finals["fuzzer"] == fz][val_col].tolist() for fz in FUZZERS}
            for f1, f2 in PAIRS:
                x, y = vals.get(f1, []), vals.get(f2, [])
                rows.append(
                    dict(
                        protocol=proto,
                        metric=metric,
                        fuzzer1=f1,
                        fuzzer2=f2,
                        a12=a12(x, y),
                        n1=len(x),
                        n2=len(y),
                        mean1=(float(np.mean(x)) if x else np.nan),
                        mean2=(float(np.mean(y)) if y else np.nan),
                    )
                )

    out = pd.DataFrame(rows)
    if args.format == "long":
        cols = ["protocol", "metric", "fuzzer1", "fuzzer2", "a12", "n1", "n2", "mean1", "mean2"]
        out = out[cols].sort_values(["protocol", "metric", "fuzzer1", "fuzzer2"])
        print(out.to_csv(index=False))
        return

    wide = out.pivot_table(index="protocol", columns=["metric", "fuzzer1", "fuzzer2"], values="a12", aggfunc="first")
    wide.columns = [f"A12_{m}_{f1}_vs_{f2}" for (m, f1, f2) in wide.columns]
    wide = wide.reset_index().sort_values("protocol")
    print(wide.to_csv(index=False))


if __name__ == "__main__":
    main()

