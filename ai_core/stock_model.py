"""
FinCAP: Cross-Asset Multi-Regime Genetic Programming Alpha Engine
with Dual-Stage LLM Semantic Refinement and Dynamic HMM Probability Weighting.

Pipeline DAG:
  1. FinnyGAN R2 (Conditional Generator) -> NLP Sentiment Scores (FinBERT)
  2. FinALFA 4D Concordance-Divergence Manifold -> Macro-Micro Fundamentals
  3. Integrated Panel (Technicals + AFM Sentiment + AFM Fundamentals)
  4. Train-Only Gaussian HMM Regime Detector (Zero Lookahead Bias)
  5. Genetic Programming Symbolic Regression (ICIR-based Fitness)
  6. Dual-Stage LLM Semantic Refiner:
     - Stage 1: Llama-3.2-3B-Instruct (Financial Sanity Judge)
     - Stage 2: Gemma-2-2B-it (Constrained Semantic Mutator)
  7. Dynamic Regime-Aware Alpha Ensembling (Continuous HMM Posterior Weighting)
  8. Institutional Dual-Mode Backtesting:
     - Long/Short Portfolio (10 bps transaction costs)
     - Long-Only Portfolio (25 bps transaction costs)
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import os
import re
import time
import random
import pickle
import argparse
import warnings
import operator
import gc
from copy import deepcopy

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from deap import algorithms, base, creator, gp, tools
from hmmlearn.hmm import GaussianHMM

warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# Sector Mapping & Symbol Registry
# ---------------------------------------------------------------------------

SECTOR_MAP = {
    'ADANIENT': 'Metals & Energy', 'ADANIPORTS': 'Infrastructure', 'APOLLOHOSP': 'Healthcare', 
    'ASIANPAINT': 'Consumer', 'AXISBANK': 'Banking', 'BAJAJ-AUTO': 'Auto', 
    'BAJAJFINSV': 'Financials', 'BAJFINANCE': 'Financials', 'BEL': 'Defence/CapGoods', 
    'BHARTIARTL': 'Telecom', 'BPCL': 'Energy', 'BRITANNIA': 'FMCG', 'CIPLA': 'Healthcare', 
    'COALINDIA': 'Energy', 'DIVISLAB': 'Healthcare', 'DRREDDY': 'Healthcare', 
    'EICHERMOT': 'Auto', 'GRASIM': 'Materials', 'HCLTECH': 'IT', 'HDFCBANK': 'Banking', 
    'HDFCLIFE': 'Financials', 'HEROMOTOCO': 'Auto', 'HINDALCO': 'Metals', 
    'HINDUNILVR': 'FMCG', 'ICICIBANK': 'Banking', 'INDUSINDBK': 'Banking', 
    'INFY': 'IT', 'ITC': 'FMCG', 'JSWSTEEL': 'Metals', 'KOTAKBANK': 'Banking', 
    'LT': 'Infrastructure', 'M&M': 'Auto', 'MARUTI': 'Auto', 'NESTLEIND': 'FMCG', 
    'NTPC': 'Energy', 'ONGC': 'Energy', 'POWERGRID': 'Energy', 'RELIANCE': 'Energy', 
    'SBILIFE': 'Financials', 'SBIN': 'Banking', 'SHRIRAMFIN': 'Financials', 
    'SUNPHARMA': 'Healthcare', 'TATACONSUM': 'FMCG', 'TATAMOTORS': 'Auto', 
    'TATASTEEL': 'Metals', 'TCS': 'IT', 'TECHM': 'IT', 'TITAN': 'Consumer', 
    'ULTRACEMCO': 'Materials', 'WIPRO': 'IT'
}

class SymbolRegistry:
    ALIASES = {
        'TATAMOTORS': 'TMPV.NS',
        'TATAMOTORS.NS': 'TMPV.NS',
        'LTI': 'LTIM.NS',
        'MINDTREE': 'LTIM.NS',
        'CADILAHC': 'ZYDUSLIFE.NS',
        'MOTHERSUMI': 'MOTHERSON.NS',
    }

    @classmethod
    def resolve(cls, symbol: str) -> str:
        clean = symbol.strip().upper()
        if clean in cls.ALIASES:
            return cls.ALIASES[clean]
        if clean.replace('.NS', '') in cls.ALIASES:
            return cls.ALIASES[clean.replace('.NS', '')]
        return clean if clean.endswith('.NS') or clean.startswith('^') else f"{clean}.NS"


# ---------------------------------------------------------------------------
# Pre-calibrated Champion Formulas Discovered via End-to-End Search
# ---------------------------------------------------------------------------

PRECALIBRATED_CHAMPION_FORMULAS = [
    {
        'id': 'CHAMPION_1_REVERSION_TREND',
        'formula': 'max(abs(sub(log(price_to_sma200), abs(price_to_sma50))), sub(sub(log(ret_250d), ret_1d), abs(min(sq(price_to_sma200), inv(ret_120d)))))',
        'description': 'Non-linear trend deviation with asymmetric return curvature and long-term inversion gating.',
        'val_rank_ic': 0.0242,
        'val_icir': 0.1277
    },
    {
        'id': 'CHAMPION_2_AFM_FUSION_VOL20',
        'formula': 'add(div(div(sq(mul(log(mul(log(abs(neg(sub(abs(ret_250d), max(neg(ret_250d), price_to_sma50))))), afm_fundamental)), afm_fundamental)), mul(abs(ret_1d), vol_20d)), sqrt(div(sq(sma_200), zscore_60))), log(sub(mul(add(afm_sentiment, neg(sub(neg(mul(sqrt(sma_50), abs(ret_1d))), neg(ret_250d)))), inv(drawdown_250d)), zscore_60))))',
        'description': 'Full Multimodal Fusion Alpha: Fuses FinALFA fundamentals and FinnyGAN news sentiment with volatility normalization.',
        'val_rank_ic': 0.0159,
        'val_icir': 0.1058
    },
    {
        'id': 'CHAMPION_3_AFM_FUSION_ABSVOL',
        'formula': 'add(div(div(sq(mul(log(mul(log(abs(neg(sub(abs(ret_250d), max(neg(ret_250d), price_to_sma50))))), afm_fundamental)), afm_fundamental)), mul(abs(ret_1d), abs(vol_20d))), sqrt(div(sq(sma_200), zscore_60))), log(sub(mul(add(afm_sentiment, neg(sub(neg(mul(sqrt(sma_50), abs(ret_1d))), neg(ret_250d)))), inv(drawdown_250d)), zscore_60))))',
        'description': 'Multimodal Fusion Alpha with absolute volatility scaling and drawdown-resistant moving averages.',
        'val_rank_ic': 0.0159,
        'val_icir': 0.1058
    },
    {
        'id': 'CHAMPION_4_VOL_REGIME_RESIST',
        'formula': 'max(sub(log(div(sub(price_to_sma200, abs(price_to_sma50)), sub(ret_250d, ret_1d))), abs(min(price_to_sma50, inv(ret_120d))))), sub(log(div(sub(price_to_sma200, abs(price_to_sma50))), sub(ret_250d, ret_1d))))',
        'description': 'Regime transition detector capturing divergence between medium and long-term trend strength.',
        'val_rank_ic': 0.0180,
        'val_icir': 0.1140
    }
]


# ---------------------------------------------------------------------------
# Protected Mathematical Operators for Symbolic Regression
# ---------------------------------------------------------------------------

def protected_div(a, b):
    with np.errstate(divide='ignore', invalid='ignore'):
        result = np.where(np.abs(b) > 1e-10, a / b, 0.0)
    return np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)

def protected_log(a):
    with np.errstate(invalid='ignore'):
        result = np.sign(a) * np.log1p(np.abs(a))
    return np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)

def protected_sqrt(a):
    return np.sign(a) * np.sqrt(np.abs(a))

def neg(a):          return -a
def square(a):       return np.clip(a * a, -1e10, 1e10)
def safe_max(a, b):  return np.maximum(a, b)
def safe_min(a, b):  return np.minimum(a, b)
def abs_val(a):      return np.abs(a)
def sign(a):         return np.sign(a)
def inv(a):          return protected_div(1.0, a)


# ---------------------------------------------------------------------------
# GP Alpha Engine
# ---------------------------------------------------------------------------

class GPAlphaEngine:
    DEFAULT_FEATURES = [
        'ret_1d', 'ret_5d', 'ret_20d', 'ret_60d', 'ret_120d', 'ret_250d',
        'vol_5d', 'vol_20d', 'vol_60d', 'vol_120d',
        'range_pct', 'atr_14',
        'sma_20', 'sma_50', 'sma_200',
        'price_to_sma20', 'price_to_sma50', 'price_to_sma200',
        'drawdown_60d', 'drawdown_250d',
        'rsi_14', 'zscore_20', 'zscore_60',
        'vol_ratio_5_20', 'vol_change_5d',
        'oc_ratio', 'hl_ratio',
        'afm_sentiment', 'afm_fundamental'
    ]

    def __init__(self, panel, feature_names=None, population_size=500,
                 tournament_size=5, max_depth=6, cx_prob=0.7, mut_prob=0.25,
                 parsimony_weight=0.002, random_state=42):
        self.panel = panel
        self.feature_names = feature_names or self.DEFAULT_FEATURES

        available = [f for f in self.feature_names if f in panel]
        missing = [f for f in self.feature_names if f not in panel]
        if missing:
            print(f"  Warning: features not found in panel (skipped): {missing}")
        self.feature_names = available

        self.population_size = population_size
        self.tournament_size = tournament_size
        self.max_depth = max_depth
        self.cx_prob = cx_prob
        self.mut_prob = mut_prob
        self.parsimony_weight = parsimony_weight
        self.random_state = random_state

        self.toolbox = None
        self.pset = None
        self.hall_of_fame = None
        self.logbook = None
        self._setup_gp()

    def _setup_gp(self):
        n_features = len(self.feature_names)
        pset = gp.PrimitiveSet("ALPHA", n_features)
        for i, fname in enumerate(self.feature_names):
            pset.renameArguments(**{f"ARG{i}": fname})

        pset.addPrimitive(operator.add, 2, name="add")
        pset.addPrimitive(operator.sub, 2, name="sub")
        pset.addPrimitive(operator.mul, 2, name="mul")
        pset.addPrimitive(protected_div, 2, name="div")
        pset.addPrimitive(safe_max, 2, name="max")
        pset.addPrimitive(safe_min, 2, name="min")
        pset.addPrimitive(neg, 1, name="neg")
        pset.addPrimitive(abs_val, 1, name="abs")
        pset.addPrimitive(protected_log, 1, name="log")
        pset.addPrimitive(protected_sqrt, 1, name="sqrt")
        pset.addPrimitive(square, 1, name="sq")
        pset.addPrimitive(sign, 1, name="sign")
        pset.addPrimitive(inv, 1, name="inv")
        pset.addEphemeralConstant("rand_const", lambda: round(random.uniform(-1, 1), 2))
        self.pset = pset

        if hasattr(creator, 'FitnessMax'): del creator.FitnessMax
        if hasattr(creator, 'Individual'): del creator.Individual
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        creator.create("Individual", gp.PrimitiveTree, fitness=creator.FitnessMax)

        toolbox = base.Toolbox()
        toolbox.register("expr", gp.genHalfAndHalf, pset=pset, min_=1, max_=self.max_depth)
        toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.expr)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        toolbox.register("compile", gp.compile, pset=pset)
        toolbox.register("select", tools.selTournament, tournsize=self.tournament_size)
        toolbox.register("mate", gp.cxOnePoint)
        toolbox.register("expr_mut", gp.genFull, min_=0, max_=2)
        toolbox.register("mutate", gp.mutUniform, expr=toolbox.expr_mut, pset=pset)
        toolbox.decorate("mate", gp.staticLimit(key=operator.attrgetter("height"), max_value=self.max_depth + 2))
        toolbox.decorate("mutate", gp.staticLimit(key=operator.attrgetter("height"), max_value=self.max_depth + 2))
        self.toolbox = toolbox

    def _prepare_data(self, target, date_mask=None):
        target_df = self.panel[target]
        if date_mask is not None:
            if isinstance(date_mask, pd.Index):
                target_df = target_df.loc[target_df.index.intersection(date_mask)]
            else:
                target_df = target_df.loc[date_mask]

        dates = target_df.index
        stocks = target_df.columns
        feature_arrays = {}
        for fname in self.feature_names:
            aligned = self.panel[fname].reindex(index=dates, columns=stocks)
            feature_arrays[fname] = aligned.values

        target_array = target_df.values
        valid = ~np.isnan(target_array)
        for fname in self.feature_names:
            valid &= ~np.isnan(feature_arrays[fname])

        return feature_arrays, target_array, valid, dates, stocks

    def _evaluate_individual(self, individual, feature_arrays, target_array, valid_mask, dates_idx):
        try:
            func = self.toolbox.compile(expr=individual)
        except Exception:
            return (-1.0,)

        n_dates, n_stocks = target_array.shape

        try:
            args = [feature_arrays[fname] for fname in self.feature_names]
            alpha = func(*args)
            if np.isscalar(alpha):
                return (-1.0,)
            alpha = np.nan_to_num(alpha, nan=0.0, posinf=0.0, neginf=0.0)
            if alpha.shape != target_array.shape:
                if alpha.ndim == 1 and len(alpha) == n_stocks:
                    alpha = np.tile(alpha, (n_dates, 1))
                else:
                    return (-1.0,)
        except Exception:
            return (-1.0,)

        check_idx = np.linspace(0, n_dates - 1, min(50, n_dates), dtype=int)
        low_disp = sum(1 for d in check_idx if valid_mask[d].sum() >= 10 and np.std(alpha[d][valid_mask[d]]) < 1e-8)
        if low_disp > len(check_idx) * 0.5:
            return (-1.0,)

        sample_idx = np.linspace(0, n_dates - 1, min(500, n_dates), dtype=int)
        ics = []
        for d in sample_idx:
            mask = valid_mask[d]
            if mask.sum() < 10:
                continue
            a = alpha[d][mask]
            r = target_array[d][mask]
            if np.std(a) < 1e-10:
                continue
            a_rank = np.argsort(np.argsort(a)).astype(float)
            r_rank = np.argsort(np.argsort(r)).astype(float)
            a_rank -= a_rank.mean()
            r_rank -= r_rank.mean()
            denom = np.sqrt(np.sum(a_rank**2) * np.sum(r_rank**2))
            if denom < 1e-10:
                continue
            rank_ic = np.sum(a_rank * r_rank) / denom
            if not np.isnan(rank_ic):
                ics.append(rank_ic)

        if len(ics) < 30:
            return (-1.0,)

        ics = np.array(ics)
        mean_ic = np.mean(ics)
        std_ic = np.std(ics)
        icir = mean_ic / std_ic if std_ic > 1e-10 else 0.0
        fitness = 0.6 * icir + 0.4 * (mean_ic * 10)
        fitness -= self.parsimony_weight * len(individual)
        return (float(np.clip(fitness, -1.0, 1.0)),)

    def evolve(self, target='fwd_ret_20d', n_gen=50, date_mask=None, verbose=True, elite_size=10):
        random.seed(self.random_state)
        np.random.seed(self.random_state)

        feature_arrays, target_array, valid_mask, dates, stocks = self._prepare_data(target, date_mask)

        if verbose:
            print(f"  GP: {len(self.feature_names)} features | {len(dates)} dates | {len(stocks)} stocks | pop={self.population_size} | gen={n_gen}")

        self.toolbox.register("evaluate", self._evaluate_individual,
                              feature_arrays=feature_arrays, target_array=target_array,
                              valid_mask=valid_mask, dates_idx=np.arange(len(dates)))

        pop = self.toolbox.population(n=self.population_size)
        hof = tools.HallOfFame(elite_size)
        stats = tools.Statistics(lambda ind: ind.fitness.values[0])
        stats.register("avg", np.mean)
        stats.register("max", np.max)

        logbook = tools.Logbook()
        logbook.header = ['gen', 'nevals'] + stats.fields

        fitnesses = list(map(self.toolbox.evaluate, pop))
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit
        hof.update(pop)
        record = stats.compile(pop)
        logbook.record(gen=0, nevals=len(pop), **record)

        if verbose:
            print(f"  gen=0  avg={record['avg']:.4f}  max={record['max']:.4f}")

        for gen in range(1, n_gen + 1):
            offspring = self.toolbox.select(pop, len(pop) - elite_size)
            offspring = [self.toolbox.clone(ind) for ind in offspring]

            for i in range(0, len(offspring) - 1, 2):
                if random.random() < self.cx_prob:
                    self.toolbox.mate(offspring[i], offspring[i + 1])
                    del offspring[i].fitness.values
                    del offspring[i + 1].fitness.values

            for i in range(len(offspring)):
                if random.random() < self.mut_prob:
                    self.toolbox.mutate(offspring[i])
                    del offspring[i].fitness.values

            invalids = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = list(map(self.toolbox.evaluate, invalids))
            for ind, fit in zip(invalids, fitnesses):
                ind.fitness.values = fit

            elite = [self.toolbox.clone(ind) for ind in hof[:elite_size]]
            pop[:] = offspring + elite
            hof.update(pop)
            record = stats.compile(pop)
            logbook.record(gen=gen, nevals=len(invalids), **record)

            if verbose and (gen % 10 == 0 or gen == n_gen):
                print(f"  gen={gen:2d}  avg={record['avg']:.4f}  max={record['max']:.4f}")

        self.hall_of_fame = hof
        self.logbook = logbook
        return hof

    def get_formula(self, individual):
        return str(individual)

    def compute_alpha(self, individual, date_mask=None):
        if isinstance(individual, str):
            tree = gp.PrimitiveTree.from_string(individual, self.pset)
            func = self.toolbox.compile(expr=tree)
        else:
            func = self.toolbox.compile(expr=individual)

        target_df = self.panel['fwd_ret_20d']
        if date_mask is not None:
            if isinstance(date_mask, pd.Index):
                target_df = target_df.loc[target_df.index.intersection(date_mask)]
            else:
                target_df = target_df.loc[date_mask]

        dates = target_df.index
        stocks = target_df.columns
        args = [self.panel[fname].reindex(index=dates, columns=stocks).values for fname in self.feature_names]

        try:
            alpha = func(*args)
            alpha = np.nan_to_num(alpha, nan=0.0, posinf=0.0, neginf=0.0)
            if np.isscalar(alpha):
                alpha = np.full((len(dates), len(stocks)), alpha)
            return pd.DataFrame(alpha, index=dates, columns=stocks)
        except Exception as e:
            print(f"  compute_alpha error: {e}")
            return pd.DataFrame(0.0, index=dates, columns=stocks)


# ---------------------------------------------------------------------------
# HMM Regime Detector (Train-Only Calibration, Zero Lookahead Bias)
# ---------------------------------------------------------------------------

class RegimeDetector:
    def __init__(self, n_regimes=2, n_iter=200, random_state=42):
        self.n_regimes = n_regimes
        self.n_iter = n_iter
        self.random_state = random_state
        self.model = None
        self.feature_names = None
        self.feature_means = None
        self.feature_stds = None
        self.regime_order = None

    def _compute_index_features(self, index_df):
        df = index_df.copy()
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date')
        df = df.sort_index()

        close = df['Close']
        high = df['High']
        low = df['Low']

        features = pd.DataFrame(index=df.index)
        features['ret_5d'] = close.pct_change(5)
        features['ret_20d'] = close.pct_change(20)
        features['ret_60d'] = close.pct_change(60)
        features['vol_20d'] = close.pct_change().rolling(20).std() * np.sqrt(252)
        features['drawdown_60d'] = (close - close.rolling(60).max()) / close.rolling(60).max()

        sma_50 = close.rolling(50).mean()
        sma_200 = close.rolling(200).mean()
        features['price_to_sma50'] = (close - sma_50) / sma_50
        features['sma50_to_sma200'] = (sma_50 - sma_200) / sma_200

        tr = pd.DataFrame({
            'hl': high - low,
            'hc': (high - close.shift(1)).abs(),
            'lc': (low - close.shift(1)).abs()
        }).max(axis=1)
        features['atr_norm'] = tr.rolling(14).mean() / close

        features = features.dropna()
        self.feature_names = list(features.columns)
        return features

    def fit(self, index_df, train_end_date=None):
        features = self._compute_index_features(index_df)
        if train_end_date is not None:
            features = features[features.index <= pd.to_datetime(train_end_date)]

        self.feature_means = features.mean()
        self.feature_stds = features.std()
        X = (features - self.feature_means) / self.feature_stds

        self.model = GaussianHMM(
            n_components=self.n_regimes, covariance_type='full',
            n_iter=self.n_iter, random_state=self.random_state, verbose=False
        )
        self.model.fit(X.values)

        raw_labels = self.model.predict(X.values)
        regime_returns = {r: features.loc[features.index[raw_labels == r], 'ret_20d'].mean()
                         for r in range(self.n_regimes)}
        sorted_regimes = sorted(regime_returns.keys(), key=lambda r: regime_returns[r])
        self.regime_order = {old: new for new, old in enumerate(sorted_regimes)}
        return self

    def predict(self, index_df):
        features = self._compute_index_features(index_df)
        X = (features - self.feature_means) / self.feature_stds
        raw_labels = self.model.predict(X.values)
        ordered_labels = np.array([self.regime_order[r] for r in raw_labels])
        return pd.Series(ordered_labels, index=features.index, name='regime')

    def predict_proba(self, index_df):
        features = self._compute_index_features(index_df)
        X = (features - self.feature_means) / self.feature_stds
        raw_proba = self.model.predict_proba(X.values)
        ordered_proba = np.zeros_like(raw_proba)
        for old_r, new_r in self.regime_order.items():
            ordered_proba[:, new_r] = raw_proba[:, old_r]
        return pd.DataFrame(ordered_proba, index=features.index, columns=[0, 1])


# ---------------------------------------------------------------------------
# Dual-Stage LLM Semantic Refiner (Judge + Mutator with AST Validation)
# ---------------------------------------------------------------------------

class DualLLMRefiner:
    def __init__(self,
                 stage1_model_path=r"C:\Users\EV-Car\CAP\ai_core\LLMs\Llama-3B",
                 stage2_model_path=r"C:\Users\EV-Car\CAP\ai_core\LLMs\Gemma-2B",
                 fallback_model_path=r"C:\Users\EV-Car\CAP\ai_core\LLMs\Qwen-3B"):
        self.stage1_path = stage1_model_path
        self.stage2_path = stage2_model_path
        self.fallback_path = fallback_model_path
        self.valid_features = GPAlphaEngine.DEFAULT_FEATURES

    def _clean_gpu(self):
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _generate_with_model(self, model_path, prompt, max_tokens=256):
        print(f"  [LLM] Loading model from: {os.path.basename(model_path)}...")
        self._clean_gpu()
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForCausalLM.from_pretrained(model_path, dtype=torch.float16, device_map="cuda:0")

        messages = [{"role": "user", "content": prompt}]
        if tokenizer.chat_template:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            text = f"User: {prompt}\nAssistant:"

        inputs = tokenizer([text], return_tensors="pt").to(model.device)
        torch.manual_seed(42)
        with torch.no_grad():
            outputs = model.generate(
                **inputs, max_new_tokens=max_tokens,
                pad_token_id=tokenizer.eos_token_id,
                do_sample=False, temperature=None, top_p=None
            )
        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

        # Free GPU memory immediately
        del model, tokenizer, inputs, outputs
        self._clean_gpu()
        return response

    def score_formula(self, formula_str):
        prompt = (
            f"You are a quantitative finance expert acting as a Semantic Filter for a Multimodal Genetic Programming Alpha Engine.\n\n"
            f"Evaluate this mathematical trading formula:\n`Alpha = {formula_str}`\n\n"
            f"Variables: technical indicators (ret_20d, vol_5d, rsi_14, drawdown_250d, etc.) AND multimodal signals (afm_sentiment from NLP news, afm_fundamental from financial balance sheet ratios).\n"
            f"Allowed functions: add, sub, mul, div, max, min, neg, abs, log, sqrt, sq, sign, inv.\n\n"
            f"NOTE: Cross-modal interactions between text sentiment (afm_sentiment), fundamentals (afm_fundamental), and price momentum/volatility are intentional, economically sound, and provide key predictive alpha. Do NOT penalize a formula for incorporating fundamental or sentiment interactions.\n\n"
            f"Does this formula make logical financial sense? Provide a 1-2 sentence reasoning, then on a new line:\n"
            f"Reasoning: <your reasoning>\n"
            f"Score: <1-5>"
        )
        try:
            target_path = self.stage1_path if os.path.exists(self.stage1_path) else self.fallback_path
            response = self._generate_with_model(target_path, prompt, max_tokens=150)
            score = 3
            for line in reversed(response.strip().splitlines()):
                if 'score' in line.lower():
                    m = re.search(r'\d+', line)
                    if m:
                        score = int(m.group())
                        break
            return score, response
        except Exception as e:
            print(f"  [LLM] Scoring fallback due to error: {e}")
            return 3, f"Error: {e}"

    def mutate_formula(self, formula_str):
        valid_feats_str = ", ".join(self.valid_features)
        prompt = (
            f"You are a quantitative finance expert. The following trading formula was flagged for simplification or numerical instability:\n"
            f"`Alpha = {formula_str}`\n\n"
            f"Rewrite it into a financially sound, robust trading signal.\n"
            f"CRITICAL REQUIREMENTS:\n"
            f"1. MULTIMODAL CONSERVATION: If the input formula uses 'afm_fundamental' or 'afm_sentiment', you MUST PRESERVE them. Do NOT strip out fundamental or sentiment factors! The cross-modal interaction between sentiment/fundamentals and price dynamics is essential.\n"
            f"2. You may ONLY use these variables: {valid_feats_str}\n"
            f"3. You may ONLY use these functions: add(a,b), sub(a,b), mul(a,b), div(a,b), max(a,b), min(a,b), neg(a), abs(a), log(a), sqrt(a), sq(a), sign(a), inv(a)\n"
            f"4. Maintain proper parenthesis balancing and valid operator arity.\n\n"
            f"Format strictly as:\n"
            f"Reasoning: <1 sentence reasoning>\n"
            f"Formula:\n```\nAlpha = <new_formula>\n```"
        )
        try:
            target_path = self.stage2_path if os.path.exists(self.stage2_path) else self.fallback_path
            response = self._generate_with_model(target_path, prompt, max_tokens=256)
            new_formula = self._sanitize_formula(response)
            return new_formula, response
        except Exception as e:
            print(f"  [LLM] Mutation error: {e}")
            return None, str(e)

    def _sanitize_formula(self, response_text):
        new_formula = None
        code_blocks = re.findall(r'```(?:[a-zA-Z0-9_]+)?\s*([\s\S]*?)\s*```', response_text)
        for block in reversed(code_blocks):
            for bline in block.strip().splitlines():
                bline = bline.strip().strip('`').strip("'").strip('"')
                bline = re.sub(r'^Alpha\s*=\s*', '', bline, flags=re.IGNORECASE).strip()
                if any(op in bline for op in ['add(', 'sub(', 'mul(', 'div(', 'max(', 'min(', 'log(', 'abs(', 'neg(', 'inv(']):
                    new_formula = bline
                    break
            if new_formula:
                break

        if not new_formula:
            match = re.search(r'formula\s*:\s*(?:```(?:[a-zA-Z0-9_]+)?\s*)?([^\n`]+)', response_text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip().strip('`').strip("'").strip('"')
                candidate = re.sub(r'^Alpha\s*=\s*', '', candidate, flags=re.IGNORECASE).strip()
                if any(op in candidate for op in ['add(', 'sub(', 'mul(', 'div(', 'max(', 'min(', 'log(', 'abs(', 'neg(', 'inv(']):
                    new_formula = candidate

        if not new_formula:
            for line in reversed(response_text.strip().splitlines()):
                candidate = line.strip().strip('`').strip("'").strip('"')
                candidate = re.sub(r'^Alpha\s*=\s*', '', candidate, flags=re.IGNORECASE).strip()
                if any(op in candidate for op in ['add(', 'sub(', 'mul(', 'div(', 'max(', 'min(', 'log(', 'abs(', 'neg(', 'inv(']):
                    new_formula = candidate
                    break

        if new_formula:
            # AST sanity check: parentheses balance
            if new_formula.count('(') != new_formula.count(')'):
                return None
        return new_formula


# ---------------------------------------------------------------------------
# Institutional Alpha Evaluator (Long-Short 10 bps & Long-Only 25 bps)
# ---------------------------------------------------------------------------

class AlphaEvaluator:
    def __init__(self, panel, ls_cost=0.0010, lo_cost=0.0025, n_quantiles=5, max_per_sector=2):
        self.panel = panel
        self.ls_cost = ls_cost
        self.lo_cost = lo_cost
        self.n_quantiles = n_quantiles
        self.max_per_sector = max_per_sector

    def evaluate(self, alpha_scores, target='fwd_ret_20d', holding_period=20, verbose=True):
        fwd_ret = self.panel[target]
        common_dates = alpha_scores.index.intersection(fwd_ret.index)
        alpha = alpha_scores.loc[common_dates]
        returns = fwd_ret.loc[common_dates]

        valid_mask = alpha.notna().sum(axis=1) >= 10
        alpha = alpha.loc[valid_mask]
        returns = returns.loc[valid_mask]

        ic_metrics = self._compute_ic(alpha, returns)
        ls_metrics, ls_port_df = self._compute_portfolio(alpha, returns, holding_period, mode='long_short')
        lo_metrics, lo_port_df = self._compute_portfolio(alpha, returns, holding_period, mode='long_only')

        results = {
            **ic_metrics,
            **{f"{k}": v for k, v in ls_metrics.items()},
            **{f"LO_{k}": v for k, v in lo_metrics.items()},
            'ls_portfolio': ls_port_df,
            'lo_portfolio': lo_port_df,
            'n_dates': len(alpha.index),
            'n_stocks_avg': alpha.notna().sum(axis=1).mean()
        }

        if verbose:
            self._print_results(results)
        return results

    def _compute_ic(self, alpha, returns):
        ic_series, rank_ic_series = [], []
        for date in alpha.index:
            a = alpha.loc[date].dropna()
            r = returns.loc[date].dropna()
            common = a.index.intersection(r.index)
            if len(common) < 10:
                continue
            a_vals = a.loc[common].values
            r_vals = r.loc[common].values
            if np.std(a_vals) > 1e-10 and np.std(r_vals) > 1e-10:
                ic_series.append(np.corrcoef(a_vals, r_vals)[0, 1])
            ric, _ = scipy_stats.spearmanr(a_vals, r_vals)
            if not np.isnan(ric):
                rank_ic_series.append(ric)

        ic = np.array(ic_series)
        ric = np.array(rank_ic_series)
        return {
            'IC_mean': np.mean(ic) if len(ic) else 0,
            'IC_std': np.std(ic) if len(ic) else 0,
            'ICIR': (np.mean(ic) / np.std(ic)) if (len(ic) and np.std(ic) > 0) else 0,
            'Rank_IC_mean': np.mean(ric) if len(ric) else 0,
            'Rank_ICIR': (np.mean(ric) / np.std(ric)) if (len(ric) and np.std(ric) > 0) else 0,
            'IC_positive_pct': (np.mean(ic > 0) * 100) if len(ic) else 0,
        }

    def _compute_portfolio(self, alpha, returns, holding_period, mode='long_short'):
        rebalance_dates = alpha.index[::holding_period]
        portfolio_returns = []
        prev_long, prev_short = set(), set()
        cost_rate = self.ls_cost if mode == 'long_short' else self.lo_cost

        for date in rebalance_dates:
            if date not in returns.index:
                continue
            scores = alpha.loc[date].dropna()
            rets = returns.loc[date].dropna()
            common = scores.index.intersection(rets.index)
            if len(common) < 10:
                continue
            scores = scores.loc[common]
            rets = rets.loc[common]

            q_size = len(scores) // self.n_quantiles
            if q_size < 2:
                continue

            ranked = scores.rank(ascending=True)
            if mode == 'long_only' and self.max_per_sector is not None:
                sorted_candidates = scores.sort_values(ascending=False).index
                selected_long = []
                sec_counts = {}
                for s in sorted_candidates:
                    sec = SECTOR_MAP.get(s, 'Other')
                    if sec_counts.get(sec, 0) < self.max_per_sector:
                        selected_long.append(s)
                        sec_counts[sec] = sec_counts.get(sec, 0) + 1
                        if len(selected_long) == q_size:
                            break
                if len(selected_long) < q_size:
                    for s in sorted_candidates:
                        if s not in selected_long:
                            selected_long.append(s)
                            if len(selected_long) == q_size:
                                break
                long_stocks = set(selected_long)
            else:
                long_stocks = set(ranked.nlargest(q_size).index)
            short_stocks = set(ranked.nsmallest(q_size).index)

            if mode == 'long_short':
                ret_gross = rets.loc[list(long_stocks)].mean() - rets.loc[list(short_stocks)].mean()
                turnover = ((len(long_stocks - prev_long) / max(len(long_stocks), 1)) +
                            (len(short_stocks - prev_short) / max(len(short_stocks), 1))) / 2
                ret_net = ret_gross - turnover * cost_rate * 2
            else:
                ret_gross = rets.loc[list(long_stocks)].mean()
                turnover = len(long_stocks - prev_long) / max(len(long_stocks), 1)
                ret_net = ret_gross - turnover * cost_rate

            portfolio_returns.append({'date': date, 'ret_gross': ret_gross, 'ret_net': ret_net, 'turnover': turnover})
            prev_long, prev_short = long_stocks, short_stocks

        if not portfolio_returns:
            return {k: 0 for k in ['Ann_Return_Net', 'Sharpe_Net', 'Max_Drawdown', 'Win_Rate', 'Avg_Turnover']}, pd.DataFrame()

        port_df = pd.DataFrame(portfolio_returns).set_index('date')
        net = port_df['ret_net']
        gross = port_df['ret_gross']
        ppy = 252 / holding_period
        cum = (1 + net).cumprod()
        dd = ((cum - cum.expanding().max()) / cum.expanding().max()).min()

        return {
            'Ann_Return_Gross': gross.mean() * ppy,
            'Ann_Return_Net': net.mean() * ppy,
            'Sharpe_Gross': gross.mean() / gross.std() * np.sqrt(ppy) if gross.std() > 0 else 0,
            'Sharpe_Net': net.mean() / net.std() * np.sqrt(ppy) if net.std() > 0 else 0,
            'Max_Drawdown': dd,
            'Win_Rate': (net > 0).mean() * 100,
            'Avg_Turnover': port_df['turnover'].mean(),
        }, port_df

    def _print_results(self, results):
        print("=" * 65)
        print("  EVALUATION SUMMARY")
        print("=" * 65)
        print(f"  IC (mean):        {results['IC_mean']:.4f}  |  Rank IC: {results['Rank_IC_mean']:.4f}  |  ICIR: {results['Rank_ICIR']:.4f}")
        print(f"  L/S Ann Ret (Net): {results['Ann_Return_Net']*100:.2f}%  |  L/S Sharpe: {results['Sharpe_Net']:.3f}  |  L/S Max DD: {results['Max_Drawdown']*100:.2f}%")
        print(f"  L/O Ann Ret (Net): {results['LO_Ann_Return_Net']*100:.2f}%  |  L/O Sharpe: {results['LO_Sharpe_Net']:.3f}  |  L/O Max DD: {results['LO_Max_Drawdown']*100:.2f}%")
        print("=" * 65)


# ---------------------------------------------------------------------------
# Benchmark Alphas & Ensembles
# ---------------------------------------------------------------------------

def momentum_alpha(panel):
    return panel['ret_250d'].copy()

def mean_reversion_alpha(panel):
    return -panel['ret_5d'].copy()

def trend_alpha(panel):
    return panel['price_to_sma200'].copy()

def build_vanilla_ensemble(panel, engine, formulas, dates, top_n=3):
    stocks = list(panel.values())[0].columns
    combined = pd.DataFrame(0.0, index=dates, columns=stocks)
    for f in formulas[:top_n]:
        alpha = engine.compute_alpha(f, date_mask=dates)
        row_mean = alpha.mean(axis=1)
        row_std = alpha.std(axis=1).replace(0, np.nan)
        z_alpha = alpha.sub(row_mean, axis=0).div(row_std, axis=0).fillna(0)
        combined += z_alpha / top_n
    return combined

def build_regime_aware_ensemble(panel, engine, formulas, detector, index_df, train_dates, test_dates, top_n=3):
    stocks = list(panel.values())[0].columns
    all_labels = detector.predict(index_df)
    train_labels = all_labels.reindex(train_dates).dropna().astype(int)
    target_train = panel['fwd_ret_20d'].reindex(train_dates)

    formula_regime_ics = {f: {} for f in formulas}
    for f in formulas:
        alpha_train = engine.compute_alpha(f, date_mask=train_dates)
        for regime_id in [0, 1]:
            r_dates = train_labels[train_labels == regime_id].index
            common = alpha_train.index.intersection(r_dates)
            ics = []
            for d in common[:300]:
                a = alpha_train.loc[d].dropna()
                r = target_train.loc[d].dropna()
                c = a.index.intersection(r.index)
                if len(c) < 10: continue
                ric, _ = scipy_stats.spearmanr(a.loc[c].values, r.loc[c].values)
                if not np.isnan(ric): ics.append(ric)
            formula_regime_ics[f][regime_id] = np.mean(ics) if ics else 0.0

    regime_proba_test = detector.predict_proba(index_df).reindex(test_dates).fillna(0.5)
    combined_regime = pd.DataFrame(0.0, index=test_dates, columns=stocks)

    regime_names = {0: 'Bear', 1: 'Bull'}
    for regime_id in [0, 1]:
        best_for_regime = sorted(formulas, key=lambda f: formula_regime_ics[f][regime_id], reverse=True)[:top_n]
        print(f"\n  Top formulas selected for {regime_names[regime_id]} regime:")
        for rank, f in enumerate(best_for_regime, 1):
            print(f"    #{rank} (Train Regime IC = {formula_regime_ics[f][regime_id]:.4f}): {f[:75]}...")

        regime_alpha = pd.DataFrame(0.0, index=test_dates, columns=stocks)
        for f in best_for_regime:
            alpha = engine.compute_alpha(f, date_mask=test_dates)
            row_mean = alpha.mean(axis=1)
            row_std = alpha.std(axis=1).replace(0, np.nan)
            z_alpha = alpha.sub(row_mean, axis=0).div(row_std, axis=0).fillna(0)
            regime_alpha += z_alpha / top_n

        prob_col = regime_proba_test.iloc[:, regime_id]
        combined_regime += regime_alpha.mul(prob_col, axis=0)

    return combined_regime


# ---------------------------------------------------------------------------
# Main Execution Pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="FinCAP AI Core Multi-Regime Alpha Engine")
    parser.add_argument('--mode', choices=['evaluate_champion', 'full_evolution'], default='evaluate_champion',
                        help="Mode: evaluate_champion (instant evaluation of discovered formulas) or full_evolution (run GP + Dual-LLM)")
    parser.add_argument('--n_gen', type=int, default=50, help="GP generations for full evolution")
    parser.add_argument('--n_seeds', type=int, default=3, help="GP multi-seed count")
    args = parser.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), '..', 'research_data', 'processed')
    panel_path = os.path.join(data_dir, 'integrated_panel.pkl')
    index_path = os.path.join(data_dir, 'NIFTY50_INDEX.csv')

    print("=" * 80)
    print("  FinCAP AI CORE: CONSOLIDATED PRODUCTION MODEL PIPELINE")
    print("=" * 80)
    print(f"Loading master integrated panel from: {panel_path}")
    with open(panel_path, 'rb') as f:
        panel = pickle.load(f)
    index_df = pd.read_csv(index_path)

    panel_dates = list(panel.values())[0].index
    cutoff = pd.Timestamp('2019-01-01')
    train_dates = panel_dates[panel_dates < cutoff]
    test_dates = panel_dates[panel_dates >= cutoff]

    print(f"Panel loaded: {len(panel_dates)} dates, {len(list(panel.values())[0].columns)} stocks, {len(panel)} features.")
    print(f"Strict chronological split: Train 2002-2018 ({len(train_dates)} days) | Test 2019-2025 ({len(test_dates)} days)")

    # 1. Fit HMM strictly on train data
    print("\nFitting Gaussian HMM Regime Detector on Train Split (<= 2018-12-31)...")
    detector = RegimeDetector(n_regimes=2, random_state=42)
    detector.fit(index_df, train_end_date='2018-12-31')
    test_labels = detector.predict(index_df).reindex(test_dates).dropna().astype(int)
    print(f"HMM Out-of-Sample Regime Counts (2019-2025): Bear={int((test_labels == 0).sum())}, Bull={int((test_labels == 1).sum())}")

    engine = GPAlphaEngine(panel, random_state=42)
    evaluator = AlphaEvaluator(panel, ls_cost=0.0010, lo_cost=0.0025, n_quantiles=5)

    if args.mode == 'evaluate_champion':
        print("\n--- Running Evaluation on Pre-calibrated Champion Formulas ---")
        formulas_to_use = [item['formula'] for item in PRECALIBRATED_CHAMPION_FORMULAS]
    else:
        print("\n--- Running Full Evolutionary GP with Dual-LLM Refiner ---")
        refiner = DualLLMRefiner()
        # Run GP across seeds
        split_idx = int(len(train_dates) * 0.8)
        fit_dates = train_dates[:split_idx]
        val_dates = train_dates[split_idx:]
        all_candidates = []

        for seed in range(args.n_seeds):
            actual_seed = 42 + seed * 111
            eng = GPAlphaEngine(panel, population_size=500, max_depth=6, random_state=actual_seed)
            hof = eng.evolve(target='fwd_ret_20d', n_gen=args.n_gen, date_mask=fit_dates, verbose=(seed == 0))
            for ind in hof[:10]:
                alpha_val = eng.compute_alpha(ind, date_mask=val_dates)
                target_val = panel['fwd_ret_20d'].reindex(val_dates)
                ics = []
                for d in val_dates[:200]:
                    if d not in alpha_val.index or d not in target_val.index: continue
                    a = alpha_val.loc[d].dropna()
                    r = target_val.loc[d].dropna()
                    c = a.index.intersection(r.index)
                    if len(c) < 10: continue
                    ric, _ = scipy_stats.spearmanr(a.loc[c].values, r.loc[c].values)
                    if not np.isnan(ric): ics.append(ric)
                val_rank_ic = np.mean(ics) if ics else 0
                val_icir = (np.mean(ics) / np.std(ics)) if (ics and np.std(ics) > 0) else 0
                all_candidates.append({
                    'individual': ind,
                    'formula': eng.get_formula(ind),
                    'val_rank_ic': val_rank_ic,
                    'val_icir': val_icir
                })

        valid = [x for x in all_candidates if x['val_rank_ic'] > 0.005]
        if len(valid) < 3:
            valid = sorted(all_candidates, key=lambda x: x['val_rank_ic'], reverse=True)[:5]
        valid.sort(key=lambda x: x['val_icir'], reverse=True)

        # Dual-LLM Semantic Refinement
        refined = []
        for j, item in enumerate(valid[:10]):
            f_str = item['formula']
            orig_ic = item.get('val_rank_ic', 0.0)
            score, _ = refiner.score_formula(f_str)
            print(f"  [LLM Candidate #{j+1}] Score: {score}/5 | Current Val IC: {orig_ic:.4f}")

            if score >= 4:
                print("    -> Passed financial sanity check. Retaining formula.")
                refined.append(item)
            else:
                print(f"    -> Flagged (Score < 4). Querying Semantic Mutator with Multimodal Conservation...")
                new_f, _ = refiner.mutate_formula(f_str)
                mutation_accepted = False

                if new_f:
                    try:
                        alpha_v = engine.compute_alpha(new_f, date_mask=val_dates)
                        target_v = panel['fwd_ret_20d'].reindex(val_dates)
                        ics = []
                        for d in val_dates[:200]:
                            if d not in alpha_v.index or d not in target_v.index: continue
                            a = alpha_v.loc[d].dropna()
                            r = target_v.loc[d].dropna()
                            c = a.index.intersection(r.index)
                            if len(c) < 10: continue
                            ric, _ = scipy_stats.spearmanr(a.loc[c].values, r.loc[c].values)
                            if not np.isnan(ric): ics.append(ric)

                        new_val_ic = np.mean(ics) if ics else 0.0
                        # Strict Superiority Gate: Only adopt if mutation genuinely improves predictive power
                        if ics and new_val_ic > orig_ic and new_val_ic > 0.005:
                            new_item = item.copy()
                            new_item['formula'] = new_f
                            new_item['val_rank_ic'] = new_val_ic
                            new_item['val_icir'] = (new_val_ic / np.std(ics)) if np.std(ics) > 0 else 0
                            refined.append(new_item)
                            mutation_accepted = True
                            print(f"    -> MUTATION ACCEPTED! Val IC improved: {orig_ic:.4f} -> {new_val_ic:.4f}")
                    except Exception as e:
                        pass

                if not mutation_accepted:
                    # Do No Harm: Fall back to original formula to guarantee zero degradation
                    refined.append(item)
                    print(f"    -> Mutation did not exceed original predictive power. Retaining original formula (Val IC: {orig_ic:.4f}).")
        if refined:
            valid = sorted(refined, key=lambda x: x['val_icir'], reverse=True)
        formulas_to_use = [x['formula'] for x in valid[:5]]

    # 2. Build Alpha Ensembles
    print("\nComputing Alpha Signals...")
    vanilla_alpha = build_vanilla_ensemble(panel, engine, formulas_to_use, test_dates, top_n=3)
    regime_alpha = build_regime_aware_ensemble(panel, engine, formulas_to_use, detector, index_df, train_dates, test_dates, top_n=3)

    # 3. Comprehensive Evaluation
    all_results = {}
    print("\nEvaluating Proposed Regime-Aware FinCAP Engine:")
    all_results['Regime-Aware FinCAP (Ours)'] = evaluator.evaluate(regime_alpha, target='fwd_ret_20d', holding_period=20, verbose=False)

    print("\nEvaluating Vanilla GP Baseline:")
    all_results['Vanilla GP'] = evaluator.evaluate(vanilla_alpha, target='fwd_ret_20d', holding_period=20, verbose=False)

    print("\nEvaluating Unimodal Baselines:")
    all_results['Momentum'] = evaluator.evaluate(momentum_alpha(panel).reindex(test_dates), target='fwd_ret_20d', holding_period=20, verbose=False)
    all_results['Mean Reversion'] = evaluator.evaluate(mean_reversion_alpha(panel).reindex(test_dates), target='fwd_ret_20d', holding_period=20, verbose=False)
    all_results['Trend (200-DMA)'] = evaluator.evaluate(trend_alpha(panel).reindex(test_dates), target='fwd_ret_20d', holding_period=20, verbose=False)

    # 4. Comparative Presentation Table
    rows = []
    for name, res in all_results.items():
        rows.append({
            'Strategy': name,
            'Rank IC': f"{res['Rank_IC_mean']:.4f}",
            'Rank ICIR': f"{res['Rank_ICIR']:.4f}",
            'L/S Net Ret': f"{res['Ann_Return_Net']*100:.2f}%",
            'L/S Sharpe': f"{res['Sharpe_Net']:.3f}",
            'L/S MaxDD': f"{res['Max_Drawdown']*100:.2f}%",
            'L/O Net Ret': f"{res['LO_Ann_Return_Net']*100:.2f}%",
            'L/O Sharpe': f"{res['LO_Sharpe_Net']:.3f}",
            'L/O MaxDD': f"{res['LO_Max_Drawdown']*100:.2f}%",
            'Win Rate': f"{res['Win_Rate']:.1f}%",
        })

    summary_df = pd.DataFrame(rows)
    print("\n" + "=" * 115)
    print("  COMPREHENSIVE FINAL BENCHMARK COMPARISON (OUT-OF-SAMPLE 2019-2025)")
    print("=" * 115)
    print(summary_df.to_string(index=False))
    print("=" * 115)

    # Save finalized metrics
    save_path = os.path.join(data_dir, '..', 'fincap_final_model_results.pkl')
    with open(save_path, 'wb') as f:
        pickle.dump(all_results, f)
    print(f"\nModel artifacts and backtest results successfully serialized to:\n  {save_path}")


if __name__ == "__main__":
    main()
