from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from jolts import analysis, forecast
from jolts.build import build
from jolts.fetch import rows_from_response
from jolts.series import all_series, parse_series_id, series_id
from jolts.transform import quality_checks, tidy

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "jolts_rates_2017_2026.csv"


def test_series_id_round_trip():
    sid = series_id("700000", "QU")
    assert sid == "JTS700000000000000QUR"
    assert parse_series_id(sid) == ("700000", "QU")
    assert len(all_series()) == 52


def test_bad_codes_raise():
    with pytest.raises(ValueError):
        series_id("999999", "QU")
    with pytest.raises(ValueError):
        parse_series_id("CES0000000001")


def test_api_response_parsing_skips_annual_and_missing():
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {"series": [{"seriesID": "JTS000000000000000QUR", "data": [
            {"year": "2026", "period": "M08", "value": "1.9"},
            {"year": "2025", "period": "M13", "value": "2.0"},
            {"year": "2025", "period": "M07", "value": "-"},
        ]}]},
    }
    assert rows_from_response(payload) == [("JTS000000000000000QUR", 2026, "M08", 1.9)]


def test_api_error_raises():
    with pytest.raises(RuntimeError):
        rows_from_response({"status": "REQUEST_NOT_PROCESSED", "message": ["limit"]})


def _toy():
    rows = []
    for m in ["JO", "HI", "QU", "LD"]:
        for mo in range(1, 13):
            rows.append((series_id("000000", m), 2019, f"M{mo:02d}", 2.0))
            rows.append((series_id("300000", m), 2019, f"M{mo:02d}", 1.0))
    return tidy(pd.DataFrame(rows, columns=["series_id", "year", "period", "value"]))


def test_tidy_dates_and_labels():
    t = _toy()
    assert t["date"].min() == pd.Timestamp("2019-01-01")
    assert set(t["industry"]) == {"Total nonfarm", "Manufacturing"}
    assert not t.loc[t["industry_code"] == "000000", "is_sector"].any()


def test_quality_checks_flag_gaps():
    t = _toy()
    t = t[~((t["industry_code"] == "300000") & (t["measure"] == "QU") & (t["date"] == "2019-06-01"))]
    checks = quality_checks(t).set_index("check")["failing"]
    assert checks["Gaps in a monthly series"] == 1


def test_churn_ratios():
    c = analysis.churn_table(_toy())
    row = c.iloc[0]
    assert row["openings_per_hire"] == 1.0
    assert row["quits_share_pct"] == 50.0


def test_ses_on_constant_series_forecasts_the_constant():
    fit = forecast.fit_ses(np.full(30, 2.5))
    assert list(fit.forecast(3)) == pytest.approx([2.5, 2.5, 2.5])


def test_holt_follows_a_trend():
    y = np.linspace(1, 4, 40)
    fc = forecast.fit_holt(y).forecast(3)
    assert fc[0] > y[-1]
    assert np.all(np.diff(fc) > 0)


def test_forecast_interval_widens():
    rng = np.random.default_rng(0)
    y = pd.Series(2 + rng.normal(0, 0.1, 48),
                  index=pd.date_range("2022-01-01", periods=48, freq="MS"))
    fc, bt, _ = forecast.forecast_series(y, h=6, holdout=12)
    width = fc["upper_80"] - fc["lower_80"]
    assert width.is_monotonic_increasing
    assert fc["date"].iloc[0] == pd.Timestamp("2026-01-01")
    assert set(bt["model"]) == {"Naive (last value)", "SES", "Holt damped"}


def test_full_build_on_real_data(tmp_path):
    res = build(RAW, tmp_path)
    assert (tmp_path / "quality_checks.csv").exists()
    assert pd.read_csv(tmp_path / "quality_checks.csv")["failing"].sum() == 0
    assert len(res["forecast"]) == 13 * 6
    for f in ["fact_jolts_rates", "dim_industry", "dim_measure", "dim_date", "fact_quits_forecast"]:
        assert (tmp_path / "powerbi" / f"{f}.csv").exists()
    fact = pd.read_csv(tmp_path / "powerbi" / "fact_jolts_rates.csv")
    assert fact["industry_code"].astype(str).str.zfill(6).isin(
        pd.read_csv(tmp_path / "powerbi" / "dim_industry.csv", dtype=str)["industry_code"]).all()
