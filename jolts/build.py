"""Build every output: checks, analysis tables, forecasts and the Power BI feed."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import analysis, forecast
from .series import INDUSTRIES, MEASURES, ROLLUPS, SHORT_NAMES
from .transform import load_raw, quality_checks, wide

HORIZON = 6
HOLDOUT = 12


def build(raw_path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    pbi = out_dir / "powerbi"
    pbi.mkdir(exist_ok=True)

    df = load_raw(raw_path)
    checks = quality_checks(df)
    checks.to_csv(out_dir / "quality_checks.csv", index=False)
    if checks["failing"].sum():
        print(checks.to_string(index=False))
        raise SystemExit("Data quality checks failed")

    compare = analysis.period_compare(df)
    compare.to_csv(out_dir / "period_compare.csv", index=False)
    churn = analysis.churn_table(df)
    churn.to_csv(out_dir / "sector_churn_latest_12m.csv", index=False)
    peaks = analysis.peaks(df)
    peaks.to_csv(out_dir / "total_nonfarm_peaks.csv", index=False)

    # Quit-rate forecast for every industry, plus a backtest table.
    quits = wide(df, "QU")
    fc_rows, bt_rows = [], []
    for code in quits.columns:
        y = quits[code].dropna()
        y = y[y.index >= "2021-01-01"]  # fit after the 2020 shock so it doesn't distort the trend
        fc, bt, fit = forecast.forecast_series(y, HORIZON, HOLDOUT)
        fc_rows.append(fc.assign(industry_code=code, industry=INDUSTRIES[code],
                                 alpha=fit.alpha, beta=fit.beta, phi=fit.phi))
        bt_rows.append(bt.assign(industry_code=code, industry=INDUSTRIES[code]))
    fc_all = pd.concat(fc_rows, ignore_index=True)
    bt_all = pd.concat(bt_rows, ignore_index=True)
    fc_all.to_csv(out_dir / "quits_forecast.csv", index=False)
    bt_all.round(4).to_csv(out_dir / "forecast_backtest.csv", index=False)

    # Power BI star schema.
    df[["date", "industry_code", "measure", "value"]].rename(columns={"value": "rate"}) \
        .to_csv(pbi / "fact_jolts_rates.csv", index=False)
    pd.DataFrame({
        "industry_code": list(INDUSTRIES),
        "industry": list(INDUSTRIES.values()),
        "industry_short": [SHORT_NAMES[c] for c in INDUSTRIES],
        "level": ["Roll-up" if c in ROLLUPS else "Sector" for c in INDUSTRIES],
    }).to_csv(pbi / "dim_industry.csv", index=False)
    pd.DataFrame({"measure": list(MEASURES), "measure_name": list(MEASURES.values())}) \
        .to_csv(pbi / "dim_measure.csv", index=False)
    dates = pd.date_range(df["date"].min(), fc_all["date"].max(), freq="MS")
    pd.DataFrame({"date": dates, "year": dates.year, "month": dates.month,
                  "month_name": dates.strftime("%b"), "year_month": dates.strftime("%Y-%m"),
                  "quarter": "Q" + dates.quarter.astype(str)}) \
        .to_csv(pbi / "dim_date.csv", index=False)
    fc_all[["date", "industry_code", "forecast", "lower_80", "upper_80", "model"]] \
        .to_csv(pbi / "fact_quits_forecast.csv", index=False)

    summary = summarize(df, compare, churn, peaks, fc_all, bt_all)
    (out_dir / "summary.md").write_text(summary)
    print(summary)
    return {"tidy": df, "compare": compare, "churn": churn, "forecast": fc_all, "backtest": bt_all}


def summarize(df, compare, churn, peaks, fc_all, bt_all) -> str:
    last = df["date"].max()
    tot = compare[compare["industry_code"] == "000000"].set_index("measure")
    sec = compare[compare["is_sector"]]
    q = sec[sec["measure"] == "QU"].sort_values("change_vs_2019_pct")
    ld = sec[sec["measure"] == "LD"].sort_values("change_vs_2019_pts", ascending=False)
    pk = peaks.set_index("measure")
    tfc = fc_all[fc_all["industry_code"] == "000000"]
    tbt = bt_all[bt_all["industry_code"] == "000000"].set_index("model")
    chosen = tfc["model"].iloc[0]
    lines = [
        f"# JOLTS turnover summary (data through {last:%B %Y})",
        "",
        "## Total nonfarm, latest 12 months vs 2019",
    ]
    for m in ["JO", "HI", "QU", "LD"]:
        r = tot.loc[m]
        lines.append(f"- {MEASURES[m]}: {r.avg_latest_12m:.2f}% vs {r.avg_2019:.2f}% in 2019 "
                     f"({r.change_vs_2019_pct:+.0f}%); 2022 avg {r.avg_2022:.2f}%")
    lines += [
        f"- Quits peaked at {pk.loc['QU','value']:.1f}% in {pk.loc['QU','date']:%b %Y}; "
        f"openings peaked at {pk.loc['JO','value']:.1f}% in {pk.loc['JO','date']:%b %Y}",
        "",
        "## Sectors: quit-rate change vs 2019",
    ]
    for _, r in q.iterrows():
        lines.append(f"- {r.industry_short}: {r.avg_2019:.2f}% -> {r.avg_latest_12m:.2f}% ({r.change_vs_2019_pct:+.0f}%)")
    lines += ["", "## Sectors with layoffs above 2019"]
    for _, r in ld[ld["change_vs_2019_pts"] > 0].iterrows():
        lines.append(f"- {r.industry_short}: {r.avg_2019:.2f}% -> {r.avg_latest_12m:.2f}% ({r.change_vs_2019_pts:+.2f} pts)")
    lines += ["", "## Openings per hire (latest 12 months, sectors)"]
    for _, r in churn.head(4).iterrows():
        lines.append(f"- {r.industry_short}: {r.openings_per_hire:.2f} openings per hire, "
                     f"{r.quits_share_pct:.0f}% of separations are quits")
    lines += [
        "",
        f"## Total nonfarm quit-rate forecast ({chosen}, fit on 2021 onward)",
        f"- Backtest on the last {HOLDOUT} months: MAE {tbt.loc[chosen,'mae']:.3f} pts "
        f"vs {tbt.loc['Naive (last value)','mae']:.3f} for the naive baseline",
    ]
    piv = bt_all.pivot(index="industry_code", columns="model", values="mae")
    wins = int((piv[["SES", "Holt damped"]].min(axis=1) < piv["Naive (last value)"]).sum())
    lines.append(f"- Across all {len(piv)} series, the better smoothing model beat the naive "
                 f"baseline in {wins}; flat series like total nonfarm are hard to beat")
    for _, r in tfc.iterrows():
        lines.append(f"- {r.date:%b %Y}: {r.forecast:.2f}% (80% range {r.lower_80:.2f}-{r.upper_80:.2f})")
    return "\n".join(lines) + "\n"
