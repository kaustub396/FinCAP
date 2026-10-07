import os
import re
import time
import random
import pickle
import warnings
import operator
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
# Protected math operators for symbolic regression
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

def neg(a):   return -a
def square(a): return np.clip(a * a, -1e10, 1e10)
def safe_max(a, b): return np.maximum(a, b)
def safe_min(a, b): return np.minimum(a, b)
def abs_val(a): return np.abs(a)
def sign(a):  return np.sign(a)
def inv(a):   return protected_div(1.0, a)


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
                 tournament_size=5, max_depth=6, cx_prob=0.7, mut_prob=0.2,
                 parsimony_weight=0.001, random_state=42):
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

    def evolve(self, target='fwd_ret_20d', n_gen=50, date_mask=None, verbose=True, elite_size=5):
        random.seed(self.random_state)
        np.random.seed(self.random_state)
        self._setup_gp()

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
                print(f"  gen={gen}  avg={record['avg']:.4f}  max={record['max']:.4f}")

        self.hall_of_fame = hof
        self.logbook = logbook

        if verbose:
            print(f"  Best fitness: {hof[0].fitness.values[0]:.4f} | Formula: {str(hof[0])}")

        return hof

    def get_formula(self, individual):
        return str(individual)

    def compute_alpha(self, individual, date_mask=None):
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
# HMM Regime Detector
# ---------------------------------------------------------------------------

class RegimeDetector:

    def __init__(self, n_regimes=2, n_iter=200, random_state=42):
        self.n_regimes = n_regimes
        self.n_iter = n_iter
        self.random_state = random_state
        self.model = None
        self.feature_names = None
        self.regime_stats = None
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

    def fit(self, index_df):
        features = self._compute_index_features(index_df)
        self.feature_means = features.mean()
        # Zero-variance guard: keep std==0 features from producing NaN (0/0)
        self.feature_stds = features.std().replace(0, 1.0)
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

        ordered_labels = np.array([self.regime_order[r] for r in raw_labels])
        self.train_dates = features.index
        self.train_labels = pd.Series(ordered_labels, index=features.index, name='regime')
        return self

    def predict(self, index_df):
        features = self._compute_index_features(index_df)
        X = (features - self.feature_means) / self.feature_stds
        raw_labels = self.model.predict(X.values)
        ordered_labels = np.array([self.regime_order[r] for r in raw_labels])
        return pd.Series(ordered_labels, index=features.index, name='regime')


# ---------------------------------------------------------------------------
# Alpha Evaluator
# ---------------------------------------------------------------------------

class AlphaEvaluator:

    def __init__(self, panel, transaction_cost=0.001, n_quantiles=5):
        self.panel = panel
        self.transaction_cost = transaction_cost
        self.n_quantiles = n_quantiles

    def evaluate(self, alpha_scores, target='fwd_ret_20d', holding_period=20, verbose=True):
        fwd_ret = self.panel[target]
        common_dates = alpha_scores.index.intersection(fwd_ret.index)
        alpha = alpha_scores.loc[common_dates]
        returns = fwd_ret.loc[common_dates]

        valid_mask = alpha.notna().sum(axis=1) >= 10
        alpha = alpha.loc[valid_mask]
        returns = returns.loc[valid_mask]

        ic_metrics = self._compute_ic(alpha, returns)
        portfolio_metrics, port_df = self._compute_portfolio(alpha, returns, holding_period)

        results = {**ic_metrics, **portfolio_metrics}
        results['portfolio_returns'] = port_df
        results['n_dates'] = len(common_dates)
        results['n_stocks_avg'] = alpha.notna().sum(axis=1).mean()

        if verbose:
            self._print_results(results)
        return results

    def _compute_ic(self, alpha, returns):
        ic_series = []
        rank_ic_series = []
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
            'ic_series': ic,
            'rank_ic_series': ric,
        }

    def _compute_portfolio(self, alpha, returns, holding_period):
        rebalance_dates = alpha.index[::holding_period]
        portfolio_returns = []
        prev_long, prev_short = set(), set()

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
            long_stocks = set(ranked.nlargest(q_size).index)
            short_stocks = set(ranked.nsmallest(q_size).index)

            ls_ret = rets.loc[list(long_stocks)].mean() - rets.loc[list(short_stocks)].mean()
            turnover = ((len(long_stocks - prev_long) / max(len(long_stocks), 1)) +
                        (len(short_stocks - prev_short) / max(len(short_stocks), 1))) / 2
            ls_ret_net = ls_ret - turnover * self.transaction_cost * 2

            portfolio_returns.append({'date': date, 'ls_ret_gross': ls_ret, 'ls_ret_net': ls_ret_net, 'turnover': turnover})
            prev_long, prev_short = long_stocks, short_stocks

        if not portfolio_returns:
            return {k: 0 for k in ['Ann_Return_Net', 'Sharpe_Net', 'Max_Drawdown', 'Win_Rate', 'Avg_Turnover', 'Num_Rebalances']}, pd.DataFrame()

        port_df = pd.DataFrame(portfolio_returns).set_index('date')
        net = port_df['ls_ret_net']
        gross = port_df['ls_ret_gross']
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
            'Num_Rebalances': len(port_df),
        }, port_df

    def _print_results(self, results):
        print("=" * 55)
        print(f"  IC (mean): {results['IC_mean']:.4f}  |  Rank IC: {results['Rank_IC_mean']:.4f}  |  ICIR: {results['ICIR']:.4f}")
        print(f"  Ann Return (net): {results['Ann_Return_Net']*100:.2f}%  |  Sharpe: {results['Sharpe_Net']:.3f}  |  Max DD: {results['Max_Drawdown']*100:.2f}%")
        print("=" * 55)


# ---------------------------------------------------------------------------
# LLM Semantic Refiner (Two-Stage)
# ---------------------------------------------------------------------------

class LLMRefiner:

    VALID_FEATURES = [
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

    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(os.path.dirname(__file__), 'LLMs', 'Qwen-3B')
        print(f"Loading refiner from: {model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float16)
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(device)
        print(f"Refiner loaded on {device}.")

    def _generate(self, prompt, max_tokens=256):
        messages = [{"role": "user", "content": "You are a quantitative finance expert.\n\n" + prompt}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        torch.manual_seed(42)
        outputs = self.model.generate(
            **inputs, max_new_tokens=max_tokens,
            pad_token_id=self.tokenizer.eos_token_id,
            do_sample=False, temperature=None, top_p=None
        )
        return self.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

    def score_formula(self, formula_str):
        prompt = (
            f"Evaluate this trading formula from a Genetic Programming engine:\n"
            f"`Alpha = {formula_str}`\n\n"
            f"Variables are standard technical indicators (ret_20d, vol_5d, rsi_14, afm_sentiment, etc.).\n"
            f"Functions: add, sub, mul, div, max, min, neg, abs, log, sqrt, sq, sign, inv.\n\n"
            f"Does this formula make financial sense? Give 1-2 sentences, then:\n"
            f"Score: <1-5>"
        )
        response = self._generate(prompt, max_tokens=150)
        score = 3
        try:
            for line in reversed(response.strip().split('\n')):
                if 'score' in line.lower():
                    m = re.search(r'\d+', line)
                    if m:
                        score = int(m.group())
                        break
        except Exception:
            pass
        return score, response

    def mutate_formula(self, formula_str):
        valid_str = ", ".join(self.VALID_FEATURES)
        prompt = (
            f"This trading formula was rejected as financially nonsensical:\n"
            f"`Alpha = {formula_str}`\n\n"
            f"Rewrite it as a sound trading signal. Rules:\n"
            f"1. Only use these variables: {valid_str}\n"
            f"2. Only use: add(a,b), sub(a,b), mul(a,b), div(a,b), max(a,b), min(a,b), neg(a), abs(a), log(a), sqrt(a), sq(a), sign(a), inv(a)\n\n"
            f"Give 1 sentence reasoning, then:\n"
            f"Formula: <new_formula>"
        )
        response = self._generate(prompt, max_tokens=256)
        new_formula = None
        try:
            for line in reversed(response.strip().split('\n')):
                if 'formula' in line.lower():
                    new_formula = line.split(':', 1)[1].strip().strip('`\'"')
                    break
            if not new_formula:
                new_formula = response.strip().split('\n')[-1].strip().strip('`\'"')
        except Exception:
            pass

        if new_formula:
            for prefix in ['```math', '```python', '```', 'Alpha = ', 'Alpha=']:
                if new_formula.startswith(prefix):
                    new_formula = new_formula[len(prefix):].strip()
            new_formula = new_formula.rstrip('`').strip()

        return new_formula, response


# ---------------------------------------------------------------------------
# Main pipeline: GP + validation + two-stage LLM refinement
# ---------------------------------------------------------------------------

def run_pipeline(panel, train_dates, n_gen=50, n_seeds=3, pop_size=500,
                 max_depth=6, parsimony=0.002, llm_refiner=None):
    split_idx = int(len(train_dates) * 0.8)
    fit_dates = train_dates[:split_idx]
    val_dates = train_dates[split_idx:]
    print(f"  Fit: {len(fit_dates)} days | Validate: {len(val_dates)} days")

    gp_params = dict(population_size=pop_size, tournament_size=5, max_depth=max_depth,
                     cx_prob=0.7, mut_prob=0.25, parsimony_weight=parsimony)

    all_individuals = []
    for seed in range(n_seeds):
        actual_seed = 42 + seed * 111
        engine = GPAlphaEngine(panel, **gp_params, random_state=actual_seed)
        hof = engine.evolve(target='fwd_ret_20d', n_gen=n_gen, date_mask=fit_dates,
                            verbose=(seed == 0), elite_size=10)

        target_val = panel['fwd_ret_20d'].reindex(val_dates)
        for ind in hof[:10]:
            alpha_val = engine.compute_alpha(ind, date_mask=val_dates)
            val_ics = []
            for d in val_dates[:200]:
                if d not in alpha_val.index or d not in target_val.index:
                    continue
                a = alpha_val.loc[d].dropna()
                r = target_val.loc[d].dropna()
                common = a.index.intersection(r.index)
                if len(common) < 10:
                    continue
                ric, _ = scipy_stats.spearmanr(a.loc[common].values, r.loc[common].values)
                if not np.isnan(ric):
                    val_ics.append(ric)

            val_ic = np.mean(val_ics) if val_ics else 0
            val_icir = (np.mean(val_ics) / np.std(val_ics)) if (val_ics and np.std(val_ics) > 0) else 0
            all_individuals.append({
                'individual': ind, 'engine': engine,
                'formula': engine.get_formula(ind),
                'train_fitness': ind.fitness.values[0],
                'val_rank_ic': val_ic, 'val_icir': val_icir,
                'tree_size': len(ind), 'seed': actual_seed,
            })

        print(f"  Seed {actual_seed}: top fitness={hof[0].fitness.values[0]:.4f}")

    valid = [x for x in all_individuals if x['val_rank_ic'] > 0.005]
    if len(valid) < 3:
        valid = sorted(all_individuals, key=lambda x: x['val_rank_ic'], reverse=True)[:5]
    valid.sort(key=lambda x: x['val_icir'], reverse=True)
    print(f"\n  Validated formulas: {len(valid)} of {len(all_individuals)} total")

    # Two-stage LLM semantic refinement
    if llm_refiner is not None and valid:
        print("\n  Starting two-stage semantic refinement...")
        from deap import gp as deap_gp
        import deap.creator as deap_creator

        refined = []
        for j, item in enumerate(valid[:10]):
            formula_str = item['formula']
            print(f"\n  Candidate #{j+1}: {formula_str}")

            score, reason = llm_refiner.score_formula(formula_str)
            print(f"  Stage 1 score: {score}/5")

            if score >= 4:
                print("  Pass. Keeping formula.")
                refined.append(item)
            else:
                print(f"  Score {score} < 4. Sending to mutator...")
                new_form, _ = llm_refiner.mutate_formula(formula_str)

                if new_form:
                    print(f"  Mutated to: {new_form}")
                    try:
                        pset = item['engine'].pset
                        new_tree = deap_gp.PrimitiveTree.from_string(new_form, pset)
                        new_ind = deap_creator.Individual(new_tree)
                        engine = item['engine']
                        alpha_val = engine.compute_alpha(new_ind, date_mask=val_dates)
                        target_val = panel['fwd_ret_20d'].reindex(val_dates)

                        val_ics = []
                        for d in val_dates[:200]:
                            if d not in alpha_val.index or d not in target_val.index:
                                continue
                            a = alpha_val.loc[d].dropna()
                            r = target_val.loc[d].dropna()
                            common = a.index.intersection(r.index)
                            if len(common) < 10:
                                continue
                            ric, _ = scipy_stats.spearmanr(a.loc[common].values, r.loc[common].values)
                            if not np.isnan(ric):
                                val_ics.append(ric)

                        if val_ics and np.mean(val_ics) > 0.001:
                            new_item = item.copy()
                            new_item.update({
                                'individual': new_ind, 'formula': new_form,
                                'val_rank_ic': np.mean(val_ics),
                                'val_icir': (np.mean(val_ics) / np.std(val_ics)) if np.std(val_ics) > 0 else 0,
                                'tree_size': len(new_ind),
                            })
                            refined.append(new_item)
                            print(f"  Mutation accepted. New val IC: {np.mean(val_ics):.4f}")
                        else:
                            print("  Mutation had poor predictive power. Discarding.")
                    except Exception as e:
                        print(f"  Could not parse mutated formula into DEAP tree: {e}")
                else:
                    print("  LLM did not return a valid formula.")

        if refined:
            valid = sorted(refined, key=lambda x: x['val_icir'], reverse=True)
            print(f"\n  Refinement done. {len(valid)} formulas retained.")
        else:
            print("\n  LLM refinement discarded all candidates. Falling back to original set.")

    return valid


def build_ensemble(panel, validated_formulas, dates, top_n=3):
    stocks = list(panel.values())[0].columns
    combined = pd.DataFrame(0.0, index=dates, columns=stocks)
    for item in validated_formulas[:top_n]:
        alpha = item['engine'].compute_alpha(item['individual'], date_mask=dates)
        row_mean = alpha.mean(axis=1)
        row_std = alpha.std(axis=1).replace(0, np.nan)
        z_alpha = alpha.sub(row_mean, axis=0).div(row_std, axis=0).fillna(0)
        combined += z_alpha / top_n
    return combined


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'research_data', 'processed')

    with open(os.path.join(data_dir, 'integrated_panel.pkl'), 'rb') as f:
        panel = pickle.load(f)

    index_df = pd.read_csv(os.path.join(data_dir, 'NIFTY50_INDEX.csv'))

    panel_dates = list(panel.values())[0].index

    regime_detector = RegimeDetector(n_regimes=2)
    regime_detector.fit(index_df)
    regimes = regime_detector.predict(index_df)
    print(f"Regime counts:\n{regimes.value_counts()}")

    cutoff = pd.Timestamp('2019-01-01')
    train_dates = panel_dates[panel_dates < cutoff]
    test_dates = panel_dates[panel_dates >= cutoff]

    try:
        refiner = LLMRefiner()
    except Exception as e:
        print(f"Could not load LLM refiner: {e}")
        refiner = None

    validated = run_pipeline(panel, train_dates, n_gen=50, n_seeds=3, llm_refiner=refiner)

    evaluator = AlphaEvaluator(panel, transaction_cost=0.001)
    ensemble = build_ensemble(panel, validated, test_dates)
    evaluator.evaluate(ensemble, target='fwd_ret_20d', holding_period=20)
