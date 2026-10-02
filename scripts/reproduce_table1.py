"""
Reproduces Table 1 ("Resolution Controversies and Price Extremity") of
resolution_risk_outline_revised.tex.

Table 1 is not what resolution_risk_event_study.py produces with its defaults
(--outcome-mode raw regresses price levels, not extremity). The two panels come
from these runs:

  Panel A (all matched contracts):
      --uma-backed-only --outcome-mode attenuation
  Panel B (resolution-risk-exposed contracts: elections, office exits,
           leader contacts, policy actions):
      --uma-backed-only --pm-resolver-proxy uma_risk_exposed --outcome-mode attenuation

Outputs (panels, timeseries, regressions, plots) go to exports/table1/ so the
existing exports are left untouched. The script prints the table in the
paper's layout and checks every reported number against the values typed into
the .tex; it exits non-zero if any differ at the paper's 4-decimal precision.

Usage (from the repo root):
    python scripts/reproduce_table1.py [--data-root data] [--skip-run]

--skip-run re-checks existing exports/table1/ CSVs without rebuilding the panel.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

PANELS = {
    "A": {
        "label": "Panel A: All matched contracts",
        "prefix": "table1_panel_a",
        "flags": ["--uma-backed-only", "--outcome-mode", "attenuation"],
    },
    "B": {
        "label": "Panel B: Resolution-risk-exposed contracts",
        "prefix": "table1_panel_b",
        "flags": [
            "--uma-backed-only",
            "--pm-resolver-proxy",
            "uma_risk_exposed",
            "--outcome-mode",
            "attenuation",
        ],
    },
}

# Table columns (1)-(4): (event, outcome).
COLUMNS = [
    ("mineral_rights", "pm_abs_from_50"),
    ("mineral_rights", "pm_abs_minus_k_abs_from_50"),
    ("zelensky_suit", "pm_abs_from_50"),
    ("zelensky_suit", "pm_abs_minus_k_abs_from_50"),
]

# Values as printed in resolution_risk_outline_revised.tex, Table 1.
PAPER = {
    "A": {
        "post_coef": [0.0010, 0.0003, 0.0197, 0.0047],
        "post_se": [0.0004, 0.0004, 0.0014, 0.0008],
        "pre_mean": [0.4564, 0.0071, 0.3728, -0.0197],
        "n_obs": [3105, 3105, 2565, 2565],
        "n_contracts": [105, 105, 57, 57],
    },
    "B": {
        "post_coef": [0.0117, 0.0012, 0.0204, 0.0147],
        "post_se": [0.0031, 0.0027, 0.0016, 0.0013],
        "pre_mean": [0.1969, 0.0356, 0.3437, -0.0596],
        "n_obs": [355, 355, 817, 817],
        "n_contracts": [12, 12, 19, 19],
    },
}

ROWS = [
    ("Post", "post_coef", "{:.4f}"),
    ("", "post_se", "({:.4f})"),
    ("Pre-event mean", "pre_mean", "{:.4f}"),
    ("Observations", "n_obs", "{:,}"),
    ("Matched contracts", "n_contracts", "{:,}"),
]


def run_panel(panel: dict, data_root: Path, out_dir: Path) -> None:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "resolution_risk_event_study.py"),
        "--data-root",
        str(data_root),
        "--exports-dir",
        str(out_dir),
        "--output-prefix",
        panel["prefix"],
        *panel["flags"],
    ]
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def load_columns(out_dir: Path, prefix: str) -> pd.DataFrame:
    regs = pd.read_csv(out_dir / f"{prefix}_regressions.csv").set_index(["event_slug", "outcome"])
    return regs.loc[COLUMNS].reset_index()


def format_value(fmt: str, value: float) -> str:
    return fmt.format(int(value)) if "," in fmt else fmt.format(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-root", default=REPO_ROOT / "data", type=Path)
    parser.add_argument("--out-dir", default=REPO_ROOT / "exports" / "table1", type=Path)
    parser.add_argument("--skip-run", action="store_true", help="Only re-check existing outputs.")
    args = parser.parse_args()

    if not args.skip_run:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for panel in PANELS.values():
            run_panel(panel, args.data_root.resolve(), args.out_dir.resolve())

    header = ["", "(1) MR |P-.5|", "(2) MR |P-.5|-|K-.5|", "(3) ZS |P-.5|", "(4) ZS |P-.5|-|K-.5|"]
    widths = [20, 15, 22, 15, 22]
    print()
    print("Table 1: Resolution Controversies and Price Extremity")
    print("".join(h.rjust(w) if i else h.ljust(w) for i, (h, w) in enumerate(zip(header, widths))))

    mismatches = []
    for key, panel in PANELS.items():
        cols = load_columns(args.out_dir, panel["prefix"])
        print(panel["label"])
        for label, field, fmt in ROWS:
            values = cols[field].tolist()
            cells = [format_value(fmt, v) for v in values]
            print(label.ljust(widths[0]) + "".join(c.rjust(w) for c, w in zip(cells, widths[1:])))
            for col_idx, (value, expected) in enumerate(zip(values, PAPER[key][field])):
                if format_value(fmt, value) != format_value(fmt, expected):
                    mismatches.append(f"Panel {key} {field} col ({col_idx + 1}): got {value}, paper {expected}")

    print()
    if mismatches:
        print("MISMATCH vs. resolution_risk_outline_revised.tex:")
        for line in mismatches:
            print("  " + line)
        sys.exit(1)
    print("All Table 1 values match resolution_risk_outline_revised.tex.")


if __name__ == "__main__":
    main()
