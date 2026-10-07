"""Deterministic synthetic market data + demo fixtures.

Used when the real processed panel (gitignored) is not present, so the
dashboard is always demonstrable. The generated panel follows the same
schema as the real one: a dict of feature DataFrames indexed by date with
stock tickers as columns, plus a target ``fwd_ret_20d`` and an OHLCV index
frame suitable for the HMM regime detector.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

N_STOCKS = 45
N_DAYS = 3900  # ~15.7 years of business days
END_DATE = "2025-12-31"

TICKER_ROOTS = [
    "RELIANCE", "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LT", "ITC",
    "HINDUNILVR", "NESTLEIND", "BHARTIARTL", "SUNPHARMA", "DRREDDY", "CIPLA",
    "APOLLOHOSP", "MARUTI", "TATAMOTORS", "MAHINDRA", "BAJAJ-AUTO",
    "EICHERMOT", "HEROMOTOCO", "TITAN", "ASIANPAINT", "ULTRACEMCO",
    "SHREECEM", "GRASIM", "ADANIENT", "ADANIPORTS", "POWERGRID", "NTPC",
    "TATAPOWER", "COALINDIA", "ONGC", "BPCL", "JSWSTEEL", "TATASTEEL",
    "HINDALCO", "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE",
    "BRITANNIA", "TRENT", "ETERNAL", "HDFCBANK",
]


def _regime_path(n: int, rng: np.random.Generator) -> np.ndarray:
    """2-state Markov chain: 0 = bull (low vol), 1 = bear (high vol)."""
    states = np.zeros(n, dtype=int)
    p_stay = np.array([0.986, 0.970])  # P(remain in current state)
    s = 0
    for t in range(1, n):
        if rng.random() > p_stay[s]:
            s = 1 - s
        states[t] = s
    return states


def build_panel(seed: int = 7) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Build a synthetic feature panel + OHLCV index frame."""
    rng = np.random.default_rng(seed)

    dates = pd.bdate_range(end=END_DATE, periods=N_DAYS)
    tickers = TICKER_ROOTS[:N_STOCKS]
    n = N_DAYS

    states = _regime_path(n, rng)
    mu = np.where(states == 0, 0.07 / 252, -0.05 / 252)
    sigma = np.where(states == 0, 0.10 / np.sqrt(252), 0.26 / np.sqrt(252))
    factor = mu + sigma * rng.standard_normal(n)

    # Two channels create exploitable structure:
    # 1) market momentum (sign flips across regimes — fragile, like real GP alphas)
    # 2) stock-level own-momentum (sign-consistent) so validated alphas keep
    #    positive OOS IC, mirroring why momentum-style factors survive testing.
    factor_dev = factor - mu
    mom = pd.Series(factor_dev).rolling(20).mean().shift(1).fillna(0.0).values

    betas = rng.uniform(0.7, 1.3, size=N_STOCKS)
    idio_sigma = 0.17 / np.sqrt(252)
    gamma = 0.9
    own_gamma = 0.25

    rets = np.empty((n, N_STOCKS))
    for i in range(N_STOCKS):
        noise = rng.standard_normal(n)
        base = betas[i] * (factor + gamma * mom) + idio_sigma * noise
        own_mom = pd.Series(base).rolling(20).mean().shift(1).fillna(0.0).values
        rets[:, i] = base + own_gamma * own_mom
    returns = pd.DataFrame(rets, index=dates, columns=tickers)

    # OHLCV per stock (close from cumulative returns; o/h/l derived)
    price0 = rng.uniform(80, 3000, size=N_STOCKS)
    close = price0 * np.exp(np.log1p(returns).cumsum())
    open_ = close.shift(1).fillna(method="bfill")
    spread = np.abs(rng.standard_normal((n, N_STOCKS))) * 0.006 + 0.002
    high = pd.DataFrame(
        np.maximum(close.values, open_.values) * (1 + spread),
        index=dates, columns=tickers,
    )
    low = pd.DataFrame(
        np.minimum(close.values, open_.values) * (1 - spread),
        index=dates, columns=tickers,
    )

    panel: dict[str, pd.DataFrame] = {}
    ret_1d = returns

    panel["ret_1d"] = ret_1d
    for w in (5, 20, 60, 120, 250):
        panel[f"ret_{w}d"] = close.pct_change(w)
    for w in (5, 20, 60, 120):
        panel[f"vol_{w}d"] = ret_1d.rolling(w).std() * np.sqrt(252)

    panel["range_pct"] = (high - low) / close
    tr = np.maximum(
        np.maximum(high - low, (high - close.shift(1)).abs()),
        (low - close.shift(1)).abs(),
    )
    panel["atr_14"] = tr.rolling(14).mean() / close

    for w in (20, 50, 200):
        sma = close.rolling(w).mean()
        panel[f"price_to_sma{w}"] = close / sma - 1.0
    # 'sma_N' features are price-to-SMA ratios (matches DEFAULT_FEATURES)
    panel["sma_20"] = close / close.rolling(20).mean() - 1.0
    panel["sma_50"] = close / close.rolling(50).mean() - 1.0
    panel["sma_200"] = close / close.rolling(200).mean() - 1.0
    for w in (60, 250):
        peak = close.rolling(w).max()
        panel[f"drawdown_{w}d"] = (close - peak) / peak

    delta = ret_1d.clip(lower=0)
    loss = (-ret_1d).clip(lower=0)
    rs = delta.ewm(alpha=1 / 14, adjust=False).mean() / loss.ewm(
        alpha=1 / 14, adjust=False).mean()
    panel["rsi_14"] = (100 - 100 / (1 + rs)) / 100.0

    for w in (20, 60):
        sma = close.rolling(w).mean()
        std = close.rolling(w).std()
        panel[f"zscore_{w}"] = (close - sma) / std

    v5, v20 = panel["vol_5d"], panel["vol_20d"]
    panel["vol_ratio_5_20"] = v5 / v20.replace(0, np.nan)
    panel["vol_change_5d"] = v5 / v5.shift(5).replace(0, np.nan) - 1.0

    panel["oc_ratio"] = (close - open_) / open_.replace(0, np.nan)
    panel["hl_ratio"] = (high - low) / low.replace(0, np.nan)

    # Adaptive Fusion Model inputs: sentiment (fast) + fundamentals (slow)
    sent = np.empty((n, N_STOCKS))
    fund = np.empty((n, N_STOCKS))
    for i in range(N_STOCKS):
        s = np.zeros(n)
        f = np.zeros(n)
        for t in range(1, n):
            s[t] = 0.82 * s[t - 1] + rng.standard_normal()
            f[t] = 0.995 * f[t - 1] + 0.05 * rng.standard_normal()
        sent[:, i], fund[:, i] = s, f
    panel["afm_sentiment"] = pd.DataFrame(sent, index=dates, columns=tickers)
    panel["afm_fundamental"] = pd.DataFrame(fund, index=dates, columns=tickers)

    # Target: forward 20-day return
    lr = np.log1p(returns)
    fwd20 = lr.iloc[::-1].rolling(20).sum().iloc[::-1].shift(-1)
    panel["fwd_ret_20d"] = np.expm1(fwd20)

    # Index frame for the HMM regime detector (median cross-section)
    idx_ret = returns.median(axis=1)
    idx_close = (1 + idx_ret).cumprod()
    idx_close = idx_close / idx_close.iloc[0] * 500.0
    half = np.abs(idx_ret) * 0.6 + 0.002
    index_df = pd.DataFrame(
        {
            "Date": dates,
            "Open": idx_close.shift(1).fillna(idx_close.iloc[0]),
            "High": idx_close * (1 + half),
            "Low": idx_close * (1 - half),
            "Close": idx_close,
        }
    )
    return panel, index_df


# ---------------------------------------------------------------------------
# Demo fixtures (shown before any run completes)
# ---------------------------------------------------------------------------

def demo_equity_curves() -> dict:
    """Deterministic illustrative curves matching the README results table."""
    rng = np.random.default_rng(11)
    dates = pd.bdate_range("2019-01-01", periods=820)[::20]  # 20-day rebalances
    specs = {
        "vanilla": (0.0162, 0.200),
        "momentum": (0.0481, 0.165),
        "hmm": (0.0841, 0.140),
        "refined": (0.1010, 0.120),
    }
    out: dict = {"dates": [d.strftime("%Y-%m-%d") for d in dates]}
    for key, (ann_ret, ann_vol) in specs.items():
        step_yrs = 20 / 252
        mu = ann_ret * step_yrs
        sig = ann_vol * np.sqrt(step_yrs)
        r = mu + sig * rng.standard_normal(len(dates))
        r += (mu - r.mean())  # nudge to the published annual return
        out[key] = np.round(np.cumprod(1 + r), 4).tolist()
    return out


def demo_formulas() -> list[dict]:
    """Example candidates shown before a real run finishes."""
    return [
        {
            "formula": "div(sub(ret_20d, ret_60d), add(vol_20d, vol_5d))",
            "val_ic": 0.0341, "val_icir": 0.41, "tree_size": 9, "seed": 42,
            "stage1_score": 5,
            "stage1_reason": "Classic risk-adjusted momentum spread; economically grounded.",
            "status": "accepted", "demo": True,
        },
        {
            "formula": "sub(div(mul(ret_5d, sign(ret_20d)), vol_20d), div(drawdown_60d, price_to_sma200))",
            "val_ic": 0.0298, "val_icir": 0.37, "tree_size": 14, "seed": 42,
            "stage1_score": 4,
            "stage1_reason": "Momentum conditioned on trend damage; plausible contrarian overlay.",
            "status": "accepted", "demo": True,
        },
        {
            "formula": "mul(sq(div(range_pct, vol_60d)), sign(sub(rsi_14, zscore_20)))",
            "val_ic": 0.0203, "val_icir": 0.24, "tree_size": 12, "seed": 153,
            "stage1_score": 2,
            "stage1_reason": "Squared range ratio has no economic justification; scale explodes.",
            "status": "repaired",
            "mutation": "div(sub(ret_20d, ret_60d), add(vol_20d, vol_5d))",
            "mutation_note": "Repaired into a bounded momentum/volatility ratio.",
            "demo": True,
        },
        {
            "formula": "neg(div(add(afm_sentiment, afm_fundamental), add(vol_5d, vol_20d)))",
            "val_ic": 0.0187, "val_icir": 0.21, "tree_size": 11, "seed": 153,
            "stage1_score": 3,
            "stage1_reason": "Unifies sentiment and fundamentals but weak normalization.",
            "status": "accepted", "demo": True,
        },
        {
            "formula": "inv(inv(mul(abs(ret_1d), sq(vol_ratio_5_20))))",
            "val_ic": 0.0121, "val_icir": 0.13, "tree_size": 8, "seed": 264,
            "stage1_score": 1,
            "stage1_reason": "Identity-wrapped and squared; pure syntactic noise, no economics.",
            "status": "discarded",
            "mutation": "div(sub(price_to_sma20, price_to_sma50), add(vol_20d, vol_60d))",
            "mutation_note": "Repair failed validation IC gate; original discarded.",
            "demo": True,
        },
    ]


def demo_coverage() -> dict:
    """Illustrative fundamentals coverage (used when the CSV is absent)."""
    return {
        "source": "demo",
        "rows": 1218,
        "companies": 58,
        "year_range": "2005-2025",
        "ratios": [
            {"name": "PE", "filled": 1043, "pct": 85.6},
            {"name": "ROE", "filled": 1151, "pct": 94.5},
            {"name": "ROCE", "filled": 892, "pct": 73.2},
            {"name": "Current Ratio", "filled": 1096, "pct": 90.0},
            {"name": "Debt/Equity", "filled": 1121, "pct": 92.0},
        ],
        "sources": ["IndianAPI.in", "Screener.in", "Apify", "MoneyControl"],
    }


