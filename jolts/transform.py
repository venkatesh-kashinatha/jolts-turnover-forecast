"""Load the raw API extract into a tidy monthly table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .series import INDUSTRIES, MEASURES, ROLLUPS, SHORT_NAMES, parse_series_id


def load_raw(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype={"series_id": str, "period": str})
    return tidy(raw)


def tidy(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per industry, measure and month, sorted by date."""
    df = raw.copy()
    df = df[df["period"].str.match(r"^M(0[1-9]|1[0-2])$")]
    parsed = df["series_id"].map(parse_series_id)
    df["industry_code"] = parsed.str[0]
    df["measure"] = parsed.str[1]
    df["date"] = pd.to_datetime(
        df["year"].astype(str) + "-" + df["period"].str[1:] + "-01"
    )
    df["industry"] = df["industry_code"].map(INDUSTRIES)
    df["industry_short"] = df["industry_code"].map(SHORT_NAMES)
    df["measure_name"] = df["measure"].map(MEASURES)
    df["is_sector"] = ~df["industry_code"].isin(ROLLUPS)
    df = df.drop_duplicates(["series_id", "date"], keep="last")
    cols = ["date", "industry_code", "industry", "industry_short", "is_sector",
            "measure", "measure_name", "value"]
    return df[cols].sort_values(["industry_code", "measure", "date"]).reset_index(drop=True)


def wide(tidy_df: pd.DataFrame, measure: str) -> pd.DataFrame:
    """Months as rows and industry codes as columns for one measure."""
    sub = tidy_df[tidy_df["measure"] == measure]
    return sub.pivot(index="date", columns="industry_code", values="value").sort_index()


def quality_checks(tidy_df: pd.DataFrame) -> pd.DataFrame:
    """Each row is one check; failing should be 0."""
    expected_series = len(INDUSTRIES) * len(MEASURES)
    months = tidy_df["date"].nunique()
    per_series = tidy_df.groupby(["industry_code", "measure"]).size()
    full_range = pd.date_range(tidy_df["date"].min(), tidy_df["date"].max(), freq="MS")
    gaps = sum(
        len(full_range.difference(g["date"]))
        for _, g in tidy_df.groupby(["industry_code", "measure"])
    )
    checks = [
        ("Missing series", expected_series - len(per_series)),
        ("Series with a different month count", int((per_series != months).sum())),
        ("Gaps in a monthly series", gaps),
        ("Missing values", int(tidy_df["value"].isna().sum())),
        ("Negative rates", int((tidy_df["value"] < 0).sum())),
        ("Rates above 100%", int((tidy_df["value"] > 100).sum())),
        ("Unknown industry codes", int(tidy_df["industry"].isna().sum())),
    ]
    return pd.DataFrame(checks, columns=["check", "failing"])
