"""Background pipeline job: HMM regimes -> GP evolution -> two-stage refinement.

The job runs in a daemon thread; state/log/results are exposed to FastAPI.
When local LLM weights are missing, Stage 1/2 fall back to a deterministic
rule-based judge and a closed-vocabulary tree mutator so the full two-stage
flow remains demonstrable (clearly labelled in the log and API output).
"""
from __future__ import annotations

import json
import pickle
import re
import sys
import threading
import traceback
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from . import config, synthetic

# stock_model.py lives in ai_core/ (flat module, not a package)
if str(config.AI_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(config.AI_CORE_DIR))

_lock = threading.Lock()
_state: dict = {
    "running": False,
    "stage": "idle",
    "progress": 0,
    "mode": None,
    "source": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
}
_log: list[dict] = []
_results: dict | None = None
_RESULTS_PATH = config.BACKEND_DIR / "results.json"

# Restore the last completed run so results survive server restarts
if _RESULTS_PATH.exists():
    try:
        with open(_RESULTS_PATH, encoding="utf-8") as _f:
            _results = json.load(_f)
    except Exception:
        _results = None


# ---------------------------------------------------------------------------
# Thread-safe accessors
# ---------------------------------------------------------------------------

def get_state() -> dict:
    with _lock:
        return dict(_state)


def get_log() -> list[dict]:
    with _lock:
        return list(_log)


def get_results() -> dict | None:
    with _lock:
        return _results


def _say(msg: str) -> None:
    print(f"[pipeline] {msg}", flush=True)
    with _lock:
        _log.append({"t": datetime.now().strftime("%H:%M:%S"), "msg": msg})


def _stage(name: str, progress: int) -> None:
    with _lock:
        _state["stage"] = name
        _state["progress"] = progress


def start_run(mode: str = "quick") -> None:
    if mode not in config.RUN_MODES:
        raise ValueError(f"unknown mode '{mode}'")
    with _lock:
        if _state["running"]:
            raise RuntimeError("A run is already in progress")
        _state.update(
            running=True, stage="starting", progress=0, mode=mode,
            source=None, started_at=datetime.now().isoformat(timespec="seconds"),
            finished_at=None, error=None,
        )
        _log.clear()
    threading.Thread(target=_run, args=(mode,), daemon=True).start()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_data():
    if config.PANEL_PATH.exists():
        with open(config.PANEL_PATH, "rb") as f:
            panel = pickle.load(f)
        index_df = pd.read_csv(config.INDEX_PATH)
        return panel, index_df, "real"
    panel, index_df = synthetic.build_panel()
    return panel, index_df, "synthetic"


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

def _val_ics(engine, individual, panel, val_dates, max_dates=150):
    """Mean Spearman rank-IC + ICIR of one individual on validation dates."""
    alpha_val = engine.compute_alpha(individual, date_mask=val_dates)
    target = panel["fwd_ret_20d"].reindex(val_dates)
    ics = []
    for d in list(val_dates)[:max_dates]:
        if d not in alpha_val.index or d not in target.index:
            continue
        a = alpha_val.loc[d].dropna()
        r = target.loc[d].dropna()
        common = a.index.intersection(r.index)
        if len(common) < 10:
            continue
        ric, _ = scipy_stats.spearmanr(a.loc[common].values, r.loc[common].values)
        if not np.isnan(ric):
            ics.append(ric)
    if not ics:
        return 0.0, 0.0
    mean = float(np.mean(ics))
    std = float(np.std(ics))
    return mean, (mean / std if std > 1e-12 else 0.0)


# ---------------------------------------------------------------------------
# Stage 1: Economic sanity judge (LLM if weights exist, else rules)
# ---------------------------------------------------------------------------

def _heuristic_score(formula: str) -> tuple[int, str]:
    """Deterministic rubric mimicking the 5-point economic validity scale."""
    score = 5
    reasons = []

    if "inv(inv(" in formula or "neg(neg(" in formula or "abs(abs(" in formula:
        score -= 2
        reasons.append("identity-wrapped operators add no economic content")
    if formula.count("sq(") >= 2:
        score -= 1
        reasons.append("repeated squaring distorts scale without justification")
    if re.search(r"(\w+), \1\)", formula):
        score -= 1
        reasons.append("redundant self-comparison (x vs x) adds no information")
    if "max(max(" in formula or "min(min(" in formula or \
            re.search(r"(max|min)\([^()]*\b(max|min)\(", formula):
        score -= 1
        reasons.append("nested extremum selection has no economic rationale")
    if formula.count("max(") + formula.count("min(") >= 3:
        score -= 1
        reasons.append("overuse of min/max masks the underlying signal")
    if "mul(" in formula and "add(" not in formula and "sub(" not in formula:
        score -= 1
        reasons.append("pure multiplicative chain compounds scale risk")
    if "afm_fundamental" in formula and "vol" in formula and "ret" not in formula:
        score -= 1
        reasons.append("mixing fundamentals with volatility lacks a return link")
    if len(formula) > 90:
        score -= 1
        reasons.append("excessive nesting makes the signal unauditable")
    if formula.count("div(") >= 3:
        score -= 1
        reasons.append("deep ratio nesting invites division instability")

    score = max(1, min(5, score))
    if not reasons:
        reasons.append("risk-adjusted combination of coherent technical features")
    return score, "; ".join(reasons).capitalize() + "."


def _stage1_judge(formula: str, refiner) -> tuple[int, str]:
    if refiner is not None:
        try:
            score, reason = refiner.score_formula(formula)
            return int(score), str(reason).strip()
        except Exception as e:
            _say(f"  LLM judge failed ({e}); using rule-based judge")
    return _heuristic_score(formula)


# ---------------------------------------------------------------------------
# Stage 2: Closed-vocabulary mutator (LLM if weights exist, else rules)
# ---------------------------------------------------------------------------

_SAFE_TEMPLATES = [
    "div(sub(ret_20d, ret_60d), add(vol_20d, vol_5d))",
    "sub(div(mul(ret_5d, sign(ret_20d)), vol_20d), div(drawdown_60d, price_to_sma200))",
    "div(sub(price_to_sma20, price_to_sma50), add(vol_20d, vol_60d))",
    "neg(div(sub(rsi_14, zscore_20), add(vol_5d, vol_20d)))",
    "sub(div(ret_20d, add(vol_20d, vol_60d)), div(drawdown_60d, range_pct))",
]


def _matching_paren(s: str, open_idx: int) -> int:
    depth = 0
    for j in range(open_idx, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return -1


def _strip_identities(formula: str) -> str:
    """Deterministic repair of identity-wrapped unary operators.

    inv(inv(X)) -> X, neg(neg(X)) -> X, abs(abs(X)) -> abs(X).
    """
    changed = True
    while changed:
        changed = False
        for op, keep_inner_call in (("inv", False), ("neg", False), ("abs", True)):
            needle = f"{op}({op}("
            i = formula.find(needle)
            if i < 0:
                continue
            first_paren = i + len(op)
            second_op = i + len(op) + 1
            second_paren = second_op + len(op)
            outer_close = _matching_paren(formula, first_paren)
            inner_close = _matching_paren(formula, second_paren)
            if outer_close < 0 or inner_close < 0:
                continue
            if keep_inner_call:
                replacement = formula[second_op: inner_close + 1]
            else:
                replacement = formula[second_paren + 1: inner_close]
            formula = formula[:i] + replacement + formula[outer_close + 1:]
            changed = True
    return formula


def _stage2_mutate(formula: str, refiner, valid_features: list[str]) -> tuple[str | None, str]:
    """Return (new_formula_or_None, provenance_note)."""
    if refiner is not None:
        try:
            new_form, _ = refiner.mutate_formula(formula)
            if new_form:
                return new_form, "LLM mutator (closed vocabulary)"
        except Exception as e:
            _say(f"  LLM mutator failed ({e}); using rule-based mutator")

    stripped = _strip_identities(formula)
    if stripped != formula and stripped.count("(") == stripped.count(")"):
        return stripped, "Rule-based repair: identity wrappers removed"

    needed = ("ret_20d", "ret_60d", "vol_20d", "vol_5d")
    if all(v in valid_features for v in needed):
        return _SAFE_TEMPLATES[0], "Rule-based rewrite: bounded momentum/volatility template"
    return None, "No safe template available"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _run(mode: str) -> None:
    """Execute the full pipeline in the background thread."""
    try:
        params = config.RUN_MODES[mode]
        _say(f"Run started (mode={mode}, params={params})")

        # -- Data ------------------------------------------------------------
        _stage("Loading data", 5)
        panel, index_df, source = _load_data()
        with _lock:
            _state["source"] = source
        origin = "real processed panel" if source == "real" else "deterministic synthetic panel"
        _say(f"Data loaded: {origin} ({len(panel)} feature blocks)")

        # -- Regimes ---------------------------------------------------------
        _stage("Fitting 2-state Gaussian HMM", 12)
        import stock_model as sm
        detector = sm.RegimeDetector(n_regimes=2)
        detector.fit(index_df)
        regimes = detector.predict(index_df)
        counts = regimes.value_counts().sort_index().to_dict()
        _say(f"HMM fitted. Regime day-counts: {dict(counts)}")

        # -- Date split ------------------------------------------------------
        all_dates = list(panel["fwd_ret_20d"].dropna().index)
        cutoff = pd.Timestamp("2019-01-01")
        train_dates = [d for d in all_dates if d < cutoff]
        test_dates = [d for d in all_dates if d >= cutoff]
        if len(train_dates) < 200 or len(test_dates) < 60:
            cut = int(len(all_dates) * 0.8)
            train_dates, test_dates = all_dates[:cut], all_dates[cut:]
        split = int(len(train_dates) * 0.8)
        fit_dates, val_dates = train_dates[:split], train_dates[split:]
        _say(f"Split: fit={len(fit_dates)} val={len(val_dates)} test={len(test_dates)} days")

        # -- GP evolution ----------------------------------------------------
        _stage("GP evolution", 20)
        gp_params = dict(
            population_size=params["pop_size"], tournament_size=5,
            max_depth=params["max_depth"], cx_prob=0.7, mut_prob=0.25,
            parsimony_weight=0.002,
        )
        candidates: list[dict] = []
        for seed_i in range(params["n_seeds"]):
            actual_seed = 42 + seed_i * 111
            engine = sm.GPAlphaEngine(panel, **gp_params, random_state=actual_seed)
            hof = engine.evolve(
                target="fwd_ret_20d", n_gen=params["n_gen"],
                date_mask=pd.Index(fit_dates), verbose=False, elite_size=5,
            )
            _say(f"Seed {actual_seed}: best train fitness = "
                 f"{hof[0].fitness.values[0]:.4f}")
            for ind in hof[:8]:
                ric, icir = _val_ics(engine, ind, panel, val_dates)
                candidates.append({
                    "engine": engine, "individual": ind,
                    "formula": str(ind), "tree_size": len(ind),
                    "seed": actual_seed,
                    "train_fitness": float(ind.fitness.values[0]),
                    "val_rank_ic": ric, "val_icir": icir,
                })
            _stage("GP evolution", 20 + int(35 * (seed_i + 1) / params["n_seeds"]))

        # -- Validation gate --------------------------------------------------
        _stage("Validation IC gate", 58)
        valid = [c for c in candidates if c["val_rank_ic"] > 0.005]
        if len(valid) < 3:
            valid = sorted(candidates, key=lambda c: c["val_rank_ic"], reverse=True)[:5]
        valid.sort(key=lambda c: c["val_icir"], reverse=True)
        valid = valid[:10]
        _say(f"Validation gate: {len(valid)} of {len(candidates)} candidates retained")


        # -- Two-stage LLM semantic refinement ---------------------------------
        refiner = None
        if config.llm_available():
            try:
                refiner = sm.LLMRefiner(model_path=str(config.LLM_DIR))
                _say("LLM refiner loaded (local weights)")
            except Exception as e:
                _say(f"LLM refiner unavailable ({e}); rule-based fallback active")
        else:
            _say("Local LLM weights not found; rule-based judge/mutator active")

        _stage("Stage 1: economic sanity judge", 66)
        for item in valid:
            score, reason = _stage1_judge(item["formula"], refiner)
            item["stage1_score"] = int(score)
            item["stage1_reason"] = reason
            _say(f"  Judge [{score}/5] {item['formula'][:70]}")

        _stage("Stage 2: closed-vocabulary mutator", 78)
        for item in valid:
            if item["stage1_score"] >= 3:
                item["status"] = "accepted"
                continue

            new_form, note = _stage2_mutate(
                item["formula"], refiner, item["engine"].feature_names)
            if not new_form:
                item["status"] = "discarded"
                item["mutation_note"] = note
                _say(f"  Mutator: no repair — {note}")
                continue
            item["mutation"] = new_form
            item["mutation_note"] = note
            try:
                from deap import gp as deap_gp
                from deap import creator as deap_creator
                new_tree = deap_gp.PrimitiveTree.from_string(
                    new_form, item["engine"].pset)
                new_ind = deap_creator.Individual(new_tree)
            except Exception as e:
                item["status"] = "discarded"
                _say(f"  AST gate rejected repair: {e}")
                continue

            ric, icir = _val_ics(item["engine"], new_ind, panel, val_dates)
            if ric > 0.001:
                item["status"] = "repaired"
                item["individual"] = new_ind
                item["formula"] = new_form
                item["val_rank_ic"] = ric
                item["val_icir"] = icir
                item["tree_size"] = len(new_ind)
                _say(f"  Repair accepted (val IC {ric:.4f}): {new_form[:70]}")
            else:
                item["status"] = "discarded"
                _say(f"  Repair failed OOS gate (val IC {ric:.4f}); discarding")

        _say(f"Refinement complete: "
             f"{sum(1 for i in valid if i.get('status') == 'accepted')} passed, "
             f"{sum(1 for i in valid if i.get('status') == 'repaired')} repaired, "
             f"{sum(1 for i in valid if i.get('status') == 'discarded')} discarded")


        # -- Ensemble + out-of-sample evaluation -------------------------------
        _stage("Out-of-sample evaluation", 88)
        test_idx = pd.Index(test_dates)
        refined_valid = [i for i in valid if i.get("status") in ("accepted", "repaired")]
        if not refined_valid:
            refined_valid = valid[:3]

        evaluator = sm.AlphaEvaluator(panel, transaction_cost=0.001)

        def _metric_block(items):
            ens = sm.build_ensemble(panel, items, test_idx, top_n=3)
            res = evaluator.evaluate(ens, target="fwd_ret_20d",
                                     holding_period=20, verbose=False)
            port = res.get("portfolio_returns")
            equity = []
            if port is not None and len(port):
                cum = (1 + port["ls_ret_net"]).cumprod()
                equity = [[d.strftime("%Y-%m-%d"), round(float(v), 4)]
                          for d, v in cum.items()]
            return {
                "ann_return": round(float(res.get("Ann_Return_Net", 0)), 4),
                "ann_return_gross": round(float(res.get("Ann_Return_Gross", 0)), 4),
                "sharpe": round(float(res.get("Sharpe_Net", 0)), 4),
                "max_drawdown": round(float(res.get("Max_Drawdown", 0)), 4),
                "win_rate": round(float(res.get("Win_Rate", 0)), 2),
                "avg_turnover": round(float(res.get("Avg_Turnover", 0)), 4),
                "ic_mean": round(float(res.get("IC_mean", 0)), 4),
                "rank_ic": round(float(res.get("Rank_IC_mean", 0)), 4),
                "icir": round(float(res.get("ICIR", 0)), 4),
                "equity": equity,
            }

        refined_metrics = _metric_block(refined_valid)
        _say(f"Refined ensemble: ann={refined_metrics['ann_return']*100:.2f}% "
             f"sharpe={refined_metrics['sharpe']:.3f} "
             f"mdd={refined_metrics['max_drawdown']*100:.2f}%")

        # Momentum baseline for on-screen comparison
        momentum_metrics = None
        try:
            mom_alpha = panel["ret_20d"].reindex(index=test_idx)
            mom_res = evaluator.evaluate(mom_alpha, target="fwd_ret_20d",
                                         holding_period=20, verbose=False)
            mom_port = mom_res.get("portfolio_returns")
            mom_equity = []
            if mom_port is not None and len(mom_port):
                cum = (1 + mom_port["ls_ret_net"]).cumprod()
                mom_equity = [[d.strftime("%Y-%m-%d"), round(float(v), 4)]
                              for d, v in cum.items()]
            momentum_metrics = {
                "ann_return": round(float(mom_res.get("Ann_Return_Net", 0)), 4),
                "sharpe": round(float(mom_res.get("Sharpe_Net", 0)), 4),
                "max_drawdown": round(float(mom_res.get("Max_Drawdown", 0)), 4),
                "ic_mean": round(float(mom_res.get("IC_mean", 0)), 4),
                "equity": mom_equity,
            }
        except Exception as e:
            _say(f"Momentum baseline failed: {e}")

        # -- Package results ---------------------------------------------------
        _stage("Packaging results", 96)
        close_series = index_df.copy()
        close_series["Date"] = pd.to_datetime(close_series["Date"])
        close_series = close_series.set_index("Date")["Close"]
        step = max(1, len(regimes) // 600)
        sampled = regimes.iloc[::step]
        regime_series = []
        for d, r in sampled.items():
            c = close_series.reindex([d]).iloc[0]
            regime_series.append(
                [d.strftime("%Y-%m-%d"),
                 0.0 if np.isnan(c) else round(float(c), 2),
                 int(r)]
            )

        formulas = [{
            "formula": item["formula"],
            "val_ic": round(float(item["val_rank_ic"]), 4),
            "val_icir": round(float(item["val_icir"]), 4),
            "tree_size": item["tree_size"],
            "seed": item["seed"],
            "stage1_score": item.get("stage1_score"),
            "stage1_reason": item.get("stage1_reason"),
            "status": item.get("status", "accepted"),
            "mutation": item.get("mutation"),
            "mutation_note": item.get("mutation_note"),
        } for item in valid]

        results = {
            "run": {
                "mode": mode,
                "source": source,
                "judge": "LLM" if refiner is not None else "rule-based",
                "fit_days": len(fit_dates),
                "val_days": len(val_dates),
                "test_days": len(test_dates),
                "candidates_total": len(candidates),
                "candidates_retained": len(valid),
                "repaired": sum(1 for i in valid if i.get("status") == "repaired"),
                "discarded": sum(1 for i in valid if i.get("status") == "discarded"),
                "params": params,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
            },
            "regimes": {
                "counts": {str(k): int(v) for k, v in counts.items()},
                "series": regime_series,
            },
            "metrics": {"refined": refined_metrics, "momentum": momentum_metrics},
            "formulas": formulas,
        }
        global _results
        persist_err = None
        with _lock:
            _results = results
            try:
                with open(_RESULTS_PATH, "w", encoding="utf-8") as fh:
                    json.dump(results, fh)
            except Exception as e:
                persist_err = e
        if persist_err is not None:
            _say(f"Warning: could not persist results: {persist_err}")
        _stage("Complete", 100)
        _say("Run complete.")

    except Exception as e:
        _say(f"ERROR: {e}")
        _say(traceback.format_exc(limit=4))
        with _lock:
            _state["error"] = str(e)
            _state["stage"] = "failed"
    finally:
        with _lock:
            _state["running"] = False
            if _state["finished_at"] is None:
                _state["finished_at"] = datetime.now().isoformat(timespec="seconds")
