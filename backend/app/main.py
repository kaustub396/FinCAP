"""FinCAP FastAPI application — REST API + static frontend hosting."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, pipeline, synthetic

app = FastAPI(
    title="FinCAP API",
    description="Genetic Programming + Two-Stage LLM Semantic Refinement — Capstone backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_weights_available": config.llm_available(),
        "real_panel_available": config.PANEL_PATH.exists(),
        "coverage_csv_available": config.COVERAGE_CSV.exists(),
        "run_modes": list(config.RUN_MODES),
    }


@app.get("/api/status")
def status() -> dict:
    state = pipeline.get_state()
    results = pipeline.get_results()
    state["has_results"] = results is not None
    return state


@app.post("/api/run/{mode}")
def start_run(mode: str) -> dict:
    if mode not in config.RUN_MODES:
        raise HTTPException(404, f"unknown mode '{mode}' (choose from {list(config.RUN_MODES)})")
    try:
        pipeline.start_run(mode)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return pipeline.get_state()


@app.get("/api/log")
def get_log() -> dict:
    return {"entries": pipeline.get_log()}


@app.get("/api/results")
def results() -> dict:
    """Live results if a run completed, otherwise demo fixtures."""
    live = pipeline.get_results()
    if live is not None:
        live["run"]["demo"] = False
        return live
    return {
        "run": {
            "demo": True,
            "source": "published",
            "judge": "LLM (paper configuration)",
            "note": "Showing published paper results. Run the pipeline for live output.",
        },
        "regimes": {"counts": None, "series": []},
        "metrics": {
            "refined": {
                "ann_return": 0.1010, "ann_return_gross": 0.1103,
                "sharpe": 0.6415, "max_drawdown": -0.1959,
                "win_rate": 54.8, "avg_turnover": 0.31,
                "ic_mean": 0.0412, "rank_ic": 0.0587, "icir": 0.71,
                "equity": [],
            },
            "momentum": {
                "ann_return": 0.0481, "sharpe": 0.4720,
                "max_drawdown": -0.3412, "ic_mean": 0.0213,
                "equity": [],
            },
        },
        "formulas": synthetic.demo_formulas(),
    }


@app.get("/api/equity")
def equity() -> dict:
    """Equity curves: live from a completed run, else demo/published curves."""
    live = pipeline.get_results()
    if live is not None:
        out: dict = {"demo": False, "curves": {}}
        for name, m in live.get("metrics", {}).items():
            if m and m.get("equity"):
                out["curves"][name] = m["equity"]
        if out["curves"]:
            return out
    curves = synthetic.demo_equity_curves()
    return {
        "demo": True,
        "curves": {k: list(zip(curves["dates"], v))
                   for k, v in curves.items() if k != "dates"},
    }


@app.get("/api/published")
def published() -> dict:
    """README results table (paper benchmark comparison)."""
    return {
        "table": [
            {"model": "Vanilla GP", "ann_return": 1.62, "sharpe": 0.4357,
             "max_drawdown": -38.45, "sp500_degradation": -35.03},
            {"model": "Momentum Baseline", "ann_return": 4.81, "sharpe": 0.4720,
             "max_drawdown": -34.12, "sp500_degradation": -42.10},
            {"model": "HMM Regime-GP", "ann_return": 8.41, "sharpe": 0.5518,
             "max_drawdown": -24.85, "sp500_degradation": -20.71},
            {"model": "Two-Stage Refined GP", "ann_return": 10.10, "sharpe": 0.6415,
             "max_drawdown": -19.59, "sp500_degradation": -6.77, "proposed": True},
        ],
        "evaluation": {
            "universe": "NSE Nifty 50 (2002–2025, 5,700 trading days)",
            "oos_markets": ["S&P 500", "SSE Composite (2019–2025)"],
            "execution_errors": "0 / 1,729 test trading days",
        },
    }


@app.get("/api/regimes")
def regimes() -> dict:
    """HMM regime timeline: live if available, else computed on synthetic index."""
    live = pipeline.get_results()
    if live is not None and live.get("regimes", {}).get("series"):
        return {"demo": False, **live["regimes"]}
    import numpy as np
    import pandas as pd
    from .pipeline import _load_data  # reuse loader
    _, index_df, source = _load_data()
    try:
        if str(config.AI_CORE_DIR) not in sys.path:
            sys.path.insert(0, str(config.AI_CORE_DIR))
        import stock_model as sm
        det = sm.RegimeDetector(n_regimes=2)
        det.fit(index_df)
        labels = det.predict(index_df)
        counts = {str(k): int(v) for k, v in labels.value_counts().sort_index().items()}
        idx = index_df.copy()
        idx["Date"] = pd.to_datetime(idx["Date"])
        close = idx.set_index("Date")["Close"]
        step = max(1, len(labels) // 600)
        series = [
            [d.strftime("%Y-%m-%d"),
             round(float(close.reindex([d]).iloc[0])
                   if not np.isnan(close.reindex([d]).iloc[0]) else 0.0, 2),
             int(r)]
            for d, r in labels.iloc[::step].items()
        ]
        return {"demo": True, "source": source, "counts": counts, "series": series}
    except Exception as e:
        raise HTTPException(500, f"regime computation failed: {e}")


@app.get("/api/coverage")
def coverage() -> dict:
    """Fundamentals coverage: real CSV if present, else demo values."""
    import csv
    if config.COVERAGE_CSV.exists():
        with open(config.COVERAGE_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        fields = ["PE", "ROE", "ROCE", "Current_Ratio", "Debt_Equity"]
        labels = {"PE": "PE", "ROE": "ROE", "ROCE": "ROCE",
                  "Current_Ratio": "Current Ratio", "Debt_Equity": "Debt/Equity"}
        total = len(rows)
        ratios = []
        for fld in fields:
            filled = sum(1 for r in rows if (r.get(fld) or "").strip())
            ratios.append({"name": labels[fld], "filled": filled,
                           "pct": round(filled / total * 100, 1) if total else 0})
        companies = len({r.get("Company") for r in rows})
        years = [int(r["Year"]) for r in rows if r.get("Year", "").isdigit()]
        return {
            "source": "research_data/scripts/output",
            "rows": total,
            "companies": companies,
            "year_range": f"{min(years)}-{max(years)}" if years else "n/a",
            "ratios": ratios,
            "sources": ["IndianAPI.in", "Screener.in", "Apify", "MoneyControl"],
        }
    return synthetic.demo_coverage()


# ---------------------------------------------------------------------------
# Static frontend (production build) — mounted last so /api wins
# ---------------------------------------------------------------------------
if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIST), html=True),
              name="frontend")
