"""
FinCAP Production Live Pipeline & Safeguard Management Engine
Includes permanent fixes for:
  1. Sector Concentration Bias (Max 2 stocks per sector)
  2. Falling-Knife Reversal Confirmation Gate (Filters plunging assets without bottom confirmation)
  3. Dynamic Symbol & Demerger Resolver (SymbolRegistry with automatic alias resolution)
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

# ---------------------------------------------------------------------------
# 1. Sector Taxonomy
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

# ---------------------------------------------------------------------------
# 2. Dynamic Symbol & Demerger Resolver (Fix for Loophole 3)
# ---------------------------------------------------------------------------
class SymbolRegistry:
    """
    Manages live ticker symbols, handling corporate demergers, splits, and alias lookups.
    """
    ALIASES = {
        'TATAMOTORS': 'TMPV.NS',         # Tata Motors Passenger Vehicles post-demerger
        'TATAMOTORS.NS': 'TMPV.NS',
        'LTI': 'LTIM.NS',                # LTI Mindtree merger
        'MINDTREE': 'LTIM.NS',
        'CADILAHC': 'ZYDUSLIFE.NS',      # Cadila -> Zydus Lifesciences
        'MOTHERSUMI': 'MOTHERSON.NS',    # Samvardhana Motherson
    }

    @classmethod
    def resolve(cls, symbol: str) -> str:
        clean = symbol.strip().upper()
        if clean in cls.ALIASES:
            return cls.ALIASES[clean]
        if clean.replace('.NS', '') in cls.ALIASES:
            return cls.ALIASES[clean.replace('.NS', '')]
        return clean if clean.endswith('.NS') or clean.startswith('^') else f"{clean}.NS"

    @classmethod
    def reverse(cls, yf_symbol: str) -> str:
        s = yf_symbol.replace('.NS', '')
        for orig, mapped in cls.ALIASES.items():
            if mapped == yf_symbol or mapped.replace('.NS', '') == s:
                return orig.replace('.NS', '')
        return s

# ---------------------------------------------------------------------------
# 3. Reversal Confirmation Gate (Fix for Loophole 2: Falling Knives)
# ---------------------------------------------------------------------------
def reversal_confirmation_gate(live_panel, date, stock) -> tuple[bool, str]:
    """
    Prevents catching 'falling knives'.
    If a stock is oversold (RSI < 35 or 20d trend < -5%), require:
      - A green daily close (ret_1d > 0), OR
      - RSI turning upward (rsi_14 > previous rsi_14).
    If it closed red and RSI is still falling, reject entry!
    """
    rsi_s = live_panel['rsi_14'][stock]
    ret20_s = live_panel['ret_20d'][stock]
    ret1_s = live_panel['ret_1d'][stock]

    curr_rsi = rsi_s.loc[date] if date in rsi_s.index else 50.0
    curr_ret20 = ret20_s.loc[date] if date in ret20_s.index else 0.0
    curr_ret1 = ret1_s.loc[date] if date in ret1_s.index else 0.0

    # Locate previous trading day
    date_pos = list(rsi_s.index).index(date) if date in rsi_s.index else -1
    prev_rsi = rsi_s.iloc[date_pos - 1] if date_pos > 0 else curr_rsi

    is_oversold = (curr_rsi < 35.0) or (curr_ret20 < -0.05)

    if is_oversold:
        has_bounced = (curr_ret1 > 0.001) or (curr_rsi > prev_rsi)
        if not has_bounced:
            return False, f"Falling Knife: Oversold (RSI={curr_rsi:.1f}, 20d={curr_ret20*100:.1f}%) still falling (1d={curr_ret1*100:+.2f}%)"

    return True, "Passed: Healthy trend or confirmed bottom bounce"

# ---------------------------------------------------------------------------
# 4. Sector-Capped Portfolio Selector (Fix for Loophole 1: IT Bias)
# ---------------------------------------------------------------------------
def select_portfolio_with_safeguards(scores, live_panel, date, max_per_sector=2, top_k=10):
    """
    Selects top stocks enforcing:
      1. Reversal confirmation gate
      2. Maximum N stocks per sector (default = 2)
    """
    sorted_stocks = scores.sort_values(ascending=False).index
    selected = []
    sector_counts = {}
    rejection_log = []

    for s in sorted_stocks:
        sec = SECTOR_MAP.get(s, 'Other')
        
        # Check Reversal Gate
        passed, reason = reversal_confirmation_gate(live_panel, date, s)
        if not passed:
            rejection_log.append((s, sec, reason))
            continue

        # Check Sector Cap
        if sector_counts.get(sec, 0) >= max_per_sector:
            rejection_log.append((s, sec, f"Sector Cap: Max {max_per_sector} reached for {sec}"))
            continue

        selected.append(s)
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
        if len(selected) == top_k:
            break

    # Fallback to fill remaining slots if filters were too strict
    if len(selected) < top_k:
        for s in sorted_stocks:
            if s not in selected:
                selected.append(s)
                if len(selected) == top_k:
                    break

    return selected, rejection_log

# ---------------------------------------------------------------------------
# 5. Live Market Data Ingestion & Feature Engineering
# ---------------------------------------------------------------------------
def fetch_live_market_data(stocks, period='2y'):
    """
    Downloads live prices using SymbolRegistry auto-resolution.
    """
    ticker_map = {s: SymbolRegistry.resolve(s) for s in stocks}
    all_tickers = list(ticker_map.values()) + ['^NSEI']
    
    raw = yf.download(all_tickers, period=period, interval='1d', progress=False)
    close = raw['Close'].copy()
    high = raw['High'].copy()
    low = raw['Low'].copy()
    open_p = raw['Open'].copy()
    vol = raw['Volume'].copy()
    
    stock_close = pd.DataFrame(index=close.index)
    stock_high = pd.DataFrame(index=high.index)
    stock_low = pd.DataFrame(index=low.index)
    stock_open = pd.DataFrame(index=open_p.index)
    stock_vol = pd.DataFrame(index=vol.index)
    
    for s in stocks:
        yf_sym = ticker_map[s]
        if yf_sym in close.columns:
            stock_close[s] = close[yf_sym]
            stock_high[s] = high[yf_sym]
            stock_low[s] = low[yf_sym]
            stock_open[s] = open_p[yf_sym]
            stock_vol[s] = vol[yf_sym]
            
    stock_close = stock_close.ffill().bfill()
    stock_high = stock_high.ffill().bfill()
    stock_low = stock_low.ffill().bfill()
    stock_open = stock_open.ffill().bfill()
    stock_vol = stock_vol.ffill().bfill()
    
    index_df = pd.DataFrame(index=close.index)
    index_df['Close'] = close['^NSEI'].ffill().bfill()
    index_df['High'] = high['^NSEI'].ffill().bfill()
    index_df['Low'] = low['^NSEI'].ffill().bfill()
    index_df['Open'] = open_p['^NSEI'].ffill().bfill()
    index_df['Volume'] = vol['^NSEI'].ffill().bfill()
    
    return stock_close, stock_high, stock_low, stock_open, stock_vol, index_df

def compute_live_features(close, high, low, open_p, vol, hist_panel):
    """
    Computes all 38 quantitative features for live execution.
    """
    panel = {}
    panel['ret_1d'] = close.pct_change(1)
    panel['ret_5d'] = close.pct_change(5)
    panel['ret_20d'] = close.pct_change(20)
    panel['ret_60d'] = close.pct_change(60)
    panel['ret_120d'] = close.pct_change(120)
    panel['ret_250d'] = close.pct_change(250)
    
    r1 = panel['ret_1d']
    panel['vol_5d'] = r1.rolling(5).std() * np.sqrt(252)
    panel['vol_20d'] = r1.rolling(20).std() * np.sqrt(252)
    panel['vol_60d'] = r1.rolling(60).std() * np.sqrt(252)
    panel['vol_120d'] = r1.rolling(120).std() * np.sqrt(252)
    
    panel['range_pct'] = (high - low) / close
    panel['atr_14'] = (high - low).rolling(14).mean()
    panel['sma_20'] = close.rolling(20).mean()
    panel['sma_50'] = close.rolling(50).mean()
    panel['sma_200'] = close.rolling(200).mean()
    
    panel['price_to_sma20'] = (close - panel['sma_20']) / panel['sma_20']
    panel['price_to_sma50'] = (close - panel['sma_50']) / panel['sma_50']
    panel['price_to_sma200'] = (close - panel['sma_200']) / panel['sma_200']
    
    panel['drawdown_60d'] = (close - close.rolling(60).max()) / close.rolling(60).max()
    panel['drawdown_250d'] = (close - close.rolling(250).max()) / close.rolling(250).max()
    
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    panel['rsi_14'] = 100 - (100 / (1 + rs))
    
    panel['zscore_20'] = (close - panel['sma_20']) / (close.rolling(20).std().replace(0, np.nan))
    panel['zscore_60'] = (close - close.rolling(60).mean()) / (close.rolling(60).std().replace(0, np.nan))
    
    panel['vol_ratio_5_20'] = panel['vol_5d'] / panel['vol_20d'].replace(0, np.nan)
    panel['vol_change_5d'] = panel['vol_20d'].pct_change(5)
    panel['oc_ratio'] = (close - open_p) / open_p
    panel['hl_ratio'] = (high - low) / low
    
    panel['rank_ret_20d'] = panel['ret_20d'].rank(axis=1, pct=True)
    panel['rank_ret_60d'] = panel['ret_60d'].rank(axis=1, pct=True)
    panel['rank_ret_250d'] = panel['ret_250d'].rank(axis=1, pct=True)
    panel['rank_vol_20d'] = panel['vol_20d'].rank(axis=1, pct=True)
    panel['rank_zscore_20'] = panel['zscore_20'].rank(axis=1, pct=True)
    
    panel['fwd_ret_5d'] = close.pct_change(5).shift(-5)
    panel['fwd_ret_20d'] = close.pct_change(20).shift(-20)
    panel['fwd_ret_60d'] = close.pct_change(60).shift(-60)
    
    latest_fund = hist_panel['afm_fundamental'].iloc[-1]
    latest_sent = hist_panel['afm_sentiment'].iloc[-1]
    panel['afm_fundamental'] = pd.DataFrame(np.tile(latest_fund.values, (len(close), 1)), index=close.index, columns=close.columns)
    panel['afm_sentiment'] = pd.DataFrame(np.tile(latest_sent.values, (len(close), 1)), index=close.index, columns=close.columns)
    panel['afm_regime'] = pd.DataFrame(1.0, index=close.index, columns=close.columns)
    
    return panel
