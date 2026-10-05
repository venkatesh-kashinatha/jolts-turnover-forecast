"""Pull JOLTS rates from the BLS Public Data API (v2).

Without a registration key the API allows 25 series and 10 years per request,
so the 52 series are requested in batches. Set BLS_API_KEY to use a free key
(https://data.bls.gov/registrationEngine/) for higher daily limits.
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import time
from pathlib import Path

from .series import all_series

API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BATCH_SIZE = 25


def _batches(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def rows_from_response(payload: dict) -> list[tuple[str, int, str, float]]:
    """Turn one API response into (series_id, year, period, value) rows.

    Skips the annual average (M13) and any missing values ("-").
    """
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API error: {payload.get('message')}")
    rows = []
    for series in payload["Results"]["series"]:
        sid = series["seriesID"]
        for obs in series["data"]:
            period = obs["period"]
            if not period.startswith("M") or period == "M13":
                continue
            try:
                value = float(obs["value"])
            except ValueError:
                continue
            rows.append((sid, int(obs["year"]), period, value))
    return rows


def fetch(start_year: int, end_year: int, api_key: str | None = None) -> list[tuple]:
    import requests  # imported here so the build step works without it

    rows = []
    for batch in _batches(all_series(), BATCH_SIZE):
        body = {"seriesid": batch, "startyear": str(start_year), "endyear": str(end_year)}
        if api_key:
            body["registrationkey"] = api_key
        resp = requests.post(API_URL, json=body, timeout=60)
        resp.raise_for_status()
        rows.extend(rows_from_response(resp.json()))
        time.sleep(1)  # be polite to the API
    return rows


def write_csv(rows: list[tuple], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r[0], -r[1], r[2]), reverse=False)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series_id", "year", "period", "value"])
        w.writerows(rows)


def main(out: Path, start_year: int | None = None, end_year: int | None = None) -> Path:
    end_year = end_year or dt.date.today().year
    start_year = start_year or end_year - 9  # 10-year window, the keyless limit
    rows = fetch(start_year, end_year, os.environ.get("BLS_API_KEY"))
    write_csv(rows, out)
    print(f"Saved {len(rows):,} observations for {len({r[0] for r in rows})} series to {out}")
    return out
