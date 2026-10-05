"""Exponential smoothing forecasts, written in NumPy so the method is visible.

Two models are fit by grid search on one-step-ahead squared error:

* SES   - simple exponential smoothing (level only)
* Holt  - damped-trend exponential smoothing (level + trend that fades out)

JOLTS rates are already seasonally adjusted, so no seasonal term is needed.
The model with the lower holdout error is used for the final forecast, and both
are compared against a naive "last value carried forward" baseline.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

ALPHAS = np.round(np.arange(0.05, 1.0, 0.05), 2)
BETAS = np.round(np.arange(0.05, 0.55, 0.05), 2)
PHIS = (0.80, 0.85, 0.90, 0.95, 0.98)


@dataclass
class Fit:
    model: str
    alpha: float
    beta: float
    phi: float
    level: float
    trend: float
    sse: float
    resid_sd: float

    def forecast(self, h: int) -> np.ndarray:
        if self.model == "SES":
            return np.repeat(self.level, h)
        damp = np.cumsum(self.phi ** np.arange(1, h + 1))
        return self.level + damp * self.trend


def _ses(y: np.ndarray, alpha: float):
    level = y[0]
    errs = np.empty(len(y) - 1)
    for t in range(1, len(y)):
        errs[t - 1] = y[t] - level
        level = alpha * y[t] + (1 - alpha) * level
    return level, errs


def _holt(y: np.ndarray, alpha: float, beta: float, phi: float):
    level, trend = y[0], y[1] - y[0]
    errs = np.empty(len(y) - 1)
    for t in range(1, len(y)):
        pred = level + phi * trend
        errs[t - 1] = y[t] - pred
        new_level = alpha * y[t] + (1 - alpha) * pred
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return level, trend, errs


def fit_ses(y) -> Fit:
    y = np.asarray(y, dtype=float)
    best = None
    for a in ALPHAS:
        level, errs = _ses(y, a)
        sse = float(np.sum(errs**2))
        if best is None or sse < best.sse:
            best = Fit("SES", a, 0.0, 1.0, level, 0.0, sse, float(np.std(errs, ddof=1)))
    return best


def fit_holt(y) -> Fit:
    y = np.asarray(y, dtype=float)
    best = None
    for a in ALPHAS:
        for b in BETAS:
            for p in PHIS:
                level, trend, errs = _holt(y, a, b, p)
                sse = float(np.sum(errs**2))
                if best is None or sse < best.sse:
                    best = Fit("Holt damped", a, b, p, level, trend, sse,
                               float(np.std(errs, ddof=1)))
    return best


def backtest(y: pd.Series, holdout: int = 12) -> pd.DataFrame:
    """Fit on all but the last `holdout` months and score the forecast."""
    train, test = y.iloc[:-holdout], y.iloc[-holdout:].to_numpy()
    preds = {
        "Naive (last value)": np.repeat(train.iloc[-1], holdout),
        "SES": fit_ses(train).forecast(holdout),
        "Holt damped": fit_holt(train).forecast(holdout),
    }
    out = []
    for name, p in preds.items():
        err = test - p
        out.append({
            "model": name,
            "mae": float(np.mean(np.abs(err))),
            "rmse": float(np.sqrt(np.mean(err**2))),
            "mape_pct": float(np.mean(np.abs(err / test)) * 100),
        })
    return pd.DataFrame(out)


def forecast_series(y: pd.Series, h: int = 6, holdout: int = 12) -> tuple[pd.DataFrame, pd.DataFrame, Fit]:
    """Pick the better of SES / Holt on the holdout, refit on all data, forecast h months.

    Returns (forecast table, backtest table, chosen fit). The 80% interval uses the
    one-step residual spread widened by sqrt(step), a simple approximation.
    """
    bt = backtest(y, holdout)
    ets = bt[bt["model"] != "Naive (last value)"]
    chosen = ets.sort_values("mae").iloc[0]["model"]
    fit = fit_ses(y) if chosen == "SES" else fit_holt(y)
    point = fit.forecast(h)
    steps = np.arange(1, h + 1)
    half = 1.2816 * fit.resid_sd * np.sqrt(steps)
    dates = pd.date_range(y.index[-1] + pd.offsets.MonthBegin(1), periods=h, freq="MS")
    fc = pd.DataFrame({
        "date": dates,
        "forecast": point.round(3),
        "lower_80": (point - half).round(3),
        "upper_80": (point + half).round(3),
        "model": fit.model,
    })
    return fc, bt, fit
