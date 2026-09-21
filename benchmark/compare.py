"""Print a before/after table from two ``query_construction.py`` result files.

    python benchmark/compare.py benchmark/results/before.json benchmark/results/after.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def fmt_ms(value) -> str:
    return "-" if value is None else f"{value:,.2f}"


def main(before_path: str, after_path: str) -> None:
    before, after = load(before_path), load(after_path)
    b, a = before["results"], after["results"]
    print(
        f"| scenario | n | {before['label']} ms | {after['label']} ms | speed-up | nodes {before['label']} | nodes {after['label']} |"
    )
    print("|---|---|---|---|---|---|---|")
    for name in b:
        if name not in a:
            continue
        bt = b[name]["total"]["min_ms"]
        at = a[name]["total"]["min_ms"]
        if bt is None or at is None:
            # a scenario that failed on one side: say which, rather than a ratio
            left = b[name].get("error", fmt_ms(bt))
            right = a[name].get("error", fmt_ms(at))
            ratio = "n/a"
        else:
            left, right = fmt_ms(bt), fmt_ms(at)
            ratio = f"{bt / at:.1f}x" if at else "-"
        print(
            f"| {name} | {b[name].get('n') or ''} | {left} | {right} | {ratio} | "
            f"{b[name].get('nodes', '')} | {a[name].get('nodes', '')} |"
        )


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
