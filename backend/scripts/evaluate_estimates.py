"""Compare the scan pipeline's weight and piece-count estimates against ground truth.

Scan real tables, weigh each resulting bin on a scale, and count its pieces by
hand. Record one row per lot in a CSV with the columns

    lot_id,measured_kg,counted_pieces

(see docs/evaluation/ground_truth.csv). This script fetches each lot's estimate
from a running backend and prints a Markdown report for the README.

    python scripts/evaluate_estimates.py ../docs/evaluation/ground_truth.csv
    python scripts/evaluate_estimates.py truth.csv --api https://reweave.alyfarghali.com
"""

import argparse
import csv
import json
import statistics
import sys
import urllib.request


def fetch_lots(api: str) -> dict[int, dict]:
    with urllib.request.urlopen(f"{api.rstrip('/')}/api/lots", timeout=30) as response:
        return {lot["id"]: lot for lot in json.load(response)}


def read_truth(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return [
            {
                "lot_id": int(row["lot_id"]),
                "measured_kg": float(row["measured_kg"]),
                "counted_pieces": int(row["counted_pieces"]),
            }
            for row in csv.DictReader(f)
            if row.get("lot_id", "").strip()
        ]


def compare(truth: list[dict], lots: dict[int, dict]) -> tuple[list[dict], list[int]]:
    rows, missing = [], []
    for t in truth:
        lot = lots.get(t["lot_id"])
        if lot is None:
            missing.append(t["lot_id"])
            continue
        estimated_kg = float(lot["weight_kg"] or 0)
        rows.append({
            **t,
            "fabric": lot["fabric_type"],
            "estimated_kg": estimated_kg,
            "estimated_pieces": int(lot["piece_count"] or 0),
            "abs_error_kg": abs(estimated_kg - t["measured_kg"]),
            "pct_error": (estimated_kg - t["measured_kg"]) / t["measured_kg"] * 100 if t["measured_kg"] else 0.0,
        })
    return rows, missing


def report(rows: list[dict]) -> str:
    abs_pct = [abs(r["pct_error"]) for r in rows]
    exact_counts = sum(r["estimated_pieces"] == r["counted_pieces"] for r in rows)
    total_counted = sum(r["counted_pieces"] for r in rows)
    total_estimated = sum(r["estimated_pieces"] for r in rows)
    lines = [
        f"Evaluated {len(rows)} bins.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Weight: mean absolute error | {statistics.mean(r['abs_error_kg'] for r in rows) * 1000:.0f} g |",
        f"| Weight: median absolute % error | {statistics.median(abs_pct):.1f}% |",
        f"| Weight: mean signed % error (bias) | {statistics.mean(r['pct_error'] for r in rows):+.1f}% |",
        f"| Pieces: bins counted exactly | {exact_counts}/{len(rows)} |",
        f"| Pieces: detected / actual | {total_estimated}/{total_counted} |",
        "",
        "| Lot | Fabric | Estimated kg | Measured kg | Error | Pieces (est / actual) |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['lot_id']} | {r['fabric']} | {r['estimated_kg']:.3f} | {r['measured_kg']:.3f} "
            f"| {r['pct_error']:+.1f}% | {r['estimated_pieces']} / {r['counted_pieces']} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("truth_csv")
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()

    truth = read_truth(args.truth_csv)
    if not truth:
        sys.exit(f"{args.truth_csv} has no rows yet.")
    rows, missing = compare(truth, fetch_lots(args.api))
    if missing:
        print(f"Skipped lots not found on {args.api}: {', '.join(map(str, missing))}", file=sys.stderr)
    if not rows:
        sys.exit("No lots matched.")
    print(report(rows))


if __name__ == "__main__":
    main()
