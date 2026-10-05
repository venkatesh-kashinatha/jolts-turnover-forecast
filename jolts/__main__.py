"""Command line: python -m jolts fetch | build"""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "jolts_rates_2017_2026.csv"
OUT = ROOT / "outputs"


def main() -> None:
    p = argparse.ArgumentParser(prog="jolts", description="BLS JOLTS turnover analysis and forecast")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download JOLTS rates from the BLS API")
    f.add_argument("--start-year", type=int)
    f.add_argument("--end-year", type=int)
    f.add_argument("--out", type=Path, default=RAW)
    b = sub.add_parser("build", help="run checks, analysis, forecasts and the Power BI feed")
    b.add_argument("--raw", type=Path, default=RAW)
    b.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()

    if args.cmd == "fetch":
        from .fetch import main as fetch_main
        fetch_main(args.out, args.start_year, args.end_year)
    else:
        from .build import build
        build(args.raw, args.out)


if __name__ == "__main__":
    main()
