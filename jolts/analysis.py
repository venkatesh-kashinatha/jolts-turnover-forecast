"""Turnover analysis: how today's labor market compares with 2019 and the 2021-22 peak."""

from __future__ import annotations

import pandas as pd

from .series import MEASURES

BASELINE_YEAR = "2019"   # last full pre-pandemic year
PEAK_YEAR = "2022"       # the "Great Resignation" year


def period_compare(tidy_df: pd.DataFrame, window: int = 12) -> pd.DataFrame:
    """Average rate per industry and measure: 2019, 2022, and the latest `window` months."""
    last = tidy_df["date"].max()
    start = last - pd.DateOffset(months=window - 1)
    t = tidy_df.copy()
    t["period"] = None
    t.loc[t["date"].dt.year.astype(str) == BASELINE_YEAR, "period"] = "avg_2019"
    t.loc[t["date"].dt.year.astype(str) == PEAK_YEAR, "period"] = "avg_2022"
    latest = t[t["date"] >= start].assign(period="avg_latest_12m")
    t = pd.concat([t.dropna(subset=["period"]), latest])
    out = (t.groupby(["industry_code", "industry", "industry_short", "is_sector", "measure", "period"])["value"]
             .mean().unstack("period").reset_index())
    out["change_vs_2019_pts"] = out["avg_latest_12m"] - out["avg_2019"]
    out["change_vs_2019_pct"] = out["change_vs_2019_pts"] / out["avg_2019"] * 100
    out["change_vs_2022_pts"] = out["avg_latest_12m"] - out["avg_2022"]
    for c in ["avg_2019", "avg_2022", "avg_latest_12m", "change_vs_2019_pts",
              "change_vs_2022_pts", "change_vs_2019_pct"]:
        out[c] = out[c].round(2)
    out.attrs["latest_window"] = (start, last)
    return out


def peaks(tidy_df: pd.DataFrame, industry_code: str = "000000") -> pd.DataFrame:
    """Highest monthly value of each measure for one industry."""
    sub = tidy_df[tidy_df["industry_code"] == industry_code]
    idx = sub.groupby("measure")["value"].idxmax()
    return sub.loc[idx, ["measure", "measure_name", "date", "value"]].reset_index(drop=True)


def churn_table(tidy_df: pd.DataFrame, window: int = 12) -> pd.DataFrame:
    """Sector view for the latest window: quits share of separations and openings per hire.

    * quits_share = quits / (quits + layoffs): how much turnover is voluntary.
    * openings_per_hire = openings rate / hires rate: above 1 means vacancies are
      not being filled as fast as they are posted.
    """
    last = tidy_df["date"].max()
    start = last - pd.DateOffset(months=window - 1)
    sub = tidy_df[(tidy_df["date"] >= start) & tidy_df["is_sector"]]
    w = sub.pivot_table(index=["industry_code", "industry_short"], columns="measure", values="value")
    w = w.reset_index()
    w["quits_share_pct"] = (w["QU"] / (w["QU"] + w["LD"]) * 100).round(1)
    w["openings_per_hire"] = (w["JO"] / w["HI"]).round(2)
    w = w.rename(columns={m: f"{m.lower()}_rate" for m in MEASURES})
    for c in ["jo_rate", "hi_rate", "qu_rate", "ld_rate"]:
        w[c] = w[c].round(2)
    return w.sort_values("openings_per_hire", ascending=False).reset_index(drop=True)
