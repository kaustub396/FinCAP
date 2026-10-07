# FinCAP: Genetic Programming with Two-Stage LLM Semantic Refinement for Quantitative Factor Discovery

Capstone Project (Semester 4-1)  
Department of Computer Science and Engineering

---

## Overview

This repository contains the codebase, research datasets, and documentation for our Capstone project on automated quantitative factor discovery.

Standard Genetic Programming (GP) often discovers formulaic trading alphas that fit historical data through in-sample noise while being economically ungrounded (e.g., computing trigonometric transformations on price levels or subtracting volume from price). Existing LLM-augmented methods rely primarily on terminal rejection, which prematurely discards promising expressions.

FinCAP addresses this by combining:
1. **Regime-Conditioned Factor Search:** A 2-state Gaussian Hidden Markov Model (HMM) that segments market volatility states and conditions GP evolutionary search.
2. **Two-Stage LLM Semantic Refiner:** 
   - **Stage 1 (Judge):** Evaluates candidate alpha formulas from the GP Hall of Fame against a 5-point economic validity rubric. Expressions scoring <= 2 are routed for revision.
   - **Stage 2 (Mutator):** Rewrites flawed expressions under a strict closed vocabulary of allowed features and operators using deterministic greedy decoding (T=0.0).
   - **Validation Guards:** Repaired formulas are validated via AST compilation and an out-of-sample Information Coefficient check before being accepted into the final ensemble.

---

## System Workflow

```
[ Market OHLCV + News Sentiment + Fundamentals ]
                       │
                       ▼
            [ 2-State Gaussian HMM ]
            ├── Bull State (Low Volatility)
            └── Bear State (High Volatility)
                       │
                       ▼
          [ Regime-Specialized GP Engine ]
          (Generates candidate alpha trees)
                       │
                       ▼
      [ Stage 1: Economic Sanity Judge ]
             (Llama-3.2-3B / Qwen-3B)
            ├── Score >= 3: Accepted (Bypasses Stage 2)
            └── Score <= 2: Flagged for repair
                       │
                       ▼
     [ Stage 2: Closed-Vocabulary Mutator ]
                  (Gemma-2-2B)
            ├── Tier 1: AST Grammar Verification
            ├── Tier 2: Validation Rank IC > 0 Check
            └── Success: Added to ensemble (Fallback on fail)
                       │
                       ▼
    [ Dollar-Neutral Long/Short Portfolio Simulation ]
```

---

## Empirical Results Summary

Evaluated on a 23-year panel of Indian Equities (NSE Nifty 50, 2002–2025, 5,700 trading days) with out-of-sample testing on the US S&P 500 and Chinese SSE Composite (2019–2025):

| Model Architecture | OOS Ann. Net Return | OOS Net Sharpe | Max Drawdown | S&P 500 Degradation |
| :--- | :---: | :---: | :---: | :---: |
| Vanilla GP | 1.62% | 0.4357 | -38.45% | -35.03% |
| Momentum Baseline | 4.81% | 0.4720 | -34.12% | -42.10% |
| HMM Regime-GP | 8.41% | 0.5518 | -24.85% | -20.71% |
| **Proposed (Two-Stage Refined GP)** | **9.61% – 10.63%** | **0.6365 – 0.6465** | **-19.59%** | **-6.77%** |

Key observations:
- Compresses out-of-sample Sharpe decay on the US S&P 500 from -35.03% (Vanilla GP) to -6.77%.
- Halves degradation collapse on Chinese equities (-46.68% vs -92.08%).
- Zero execution errors across all 1,729 test trading days due to AST syntax gating.

---

## Repository Structure

```
FinCAP/
├── README.md                          # Project documentation
├── requirements.txt                   # Backend dependencies
│
├── ai_core/                           # Core algorithmic pipeline
│   ├── stock_model.py                 # DataProcessor + GPAlphaEngine + HMM regime fit
│   ├── train_regime.py                # HMM regime fit
│   ├── train_gp.py                    # GP evolution loop
│   ├── refine.py                      # Two-stage semantic refinement (judge + mutator)
│   ├── evaluate.py                    # OOS evaluation (Sharpe, IC, Drawdown)
│   ├── index.py                       # Index frame construction
│   ├── features.py                    # Feature engineering
│   └── LLMs/                          # Local model setup (weights gitignored)
│       └── LLMs.ipynb                 # Weight download & testing notebook
│
├── backend/                           # FastAPI + dashboard backend
│   ├── app/
│   │   ├── main.py                    # FastAPI app + static mount of frontend/dist
│   │   ├── pipeline.py                # Orchestration: HMM → GP → val IC gate → refine → ensemble OOS
│   │   ├── synthetic.py               # Synthetic demo panel + fixtures (demo fallback)
│   │   └── config.py                  # Paths, modes, LLM-availability flag
│   ├── requirements.txt
│   └── results.json                   # Generated run results (restored at startup)
│
├── frontend/                          # React 18 + Vite + Recharts dashboard
│   ├── src/pages/                     # Overview, Pipeline, Formulas, Regimes, Data
│   ├── package.json
│   └── vite.config.js                 # /api proxy → backend
│
├── research_data/                     # Data acquisition & preprocessing (gitignored)
│   ├── scripts/                       # Raw extraction, standardization, feature building
│   └── processed/                     # Panel .pkl/.csv + coverage_ratios.csv (PLACEHOLDERS)
│
├── documentation/                     # Paper drafts
│   ├── ACCESS_latex_template_20240429/access.tex + access.pdf
│   └── Architecture/ablation diagrams
│
└── â”œâ”€â”€ .gitignore
â””â”€â”€ scripts/
    â”œâ”€â”€ check_weights.py        # LLM weight verification (see §3)

```

---

## Setup & reproduction (this workspace)

### 1. Dependencies
```powershell
pip install -r requirements.txt     # deap, hmmlearn (+ numpy/pandas/torch-CPU/transformers)
```

### 2. Models (optional — upgrades the judge)
Run `ai_core/LLMs/LLMs.ipynb` to download quantized weights locally under `ai_core/LLMs/`
(gitignored). When the weight dir exists, `GET /api/health` reports `llm_weights_available: true`
and the LLM judge activates; otherwise the rule-based judge runs.

### 3. Upload your weights (optional — zero-config)
After `pip install -r requirements.txt` this is the only setup you need:

1. Export your quantized model from HuggingFace as a folder containing at least:
   - `config.json` (model config)
   - tokenizer files (`tokenizer.json` / `tokenizer.model` / `tokenizer_config.json`)
   - a weights file (`model.safetensors`, `pytorch_model.bin` or `model.bin`)
   The demo configuration uses Qwen-3B for both judge and mutator; a 4-bit/GPTQ export is ~6.5 GB.
2. Place the folder contents into `ai_core/LLMs/Qwen-3B/`. Prefer a custom mount path?
   Set `FINCAP_LLM_DIR` before starting the server, e.g.
   `FINCAP_LLM_DIR=C:\models\Qwen-3B uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir ..`
3. Verify the upload:
   `python scripts\check_weights.py`   # prints [OK] on every category, exit status 0
4. Start the server (see §1). The backend re-checks the weight folder on every request,
   so `GET /api/health` flips to `llm_weights_available: true` and the dashboard switches
   from the rule-based judge to the local LLM judge automatically — no restart, no config
   edits, no manual steps.

Notes:
- The demo configuration runs the same uploaded Qwen-3B weights for both the Stage-1
  economic judge and the Stage-2 closed-vocabulary mutator (single-model mode).
- Weights are gitignored: only `config.json` + tokenizer + weights need to sit in the
  folder. A partial upload is reported per-category by the check script, so you always
  know exactly what to copy.
- If the folder is absent when a pipeline starts, that run uses the rule-based judge; a
  re-run after upload activates the LLM judge automatically.

### 4. Run modes (backend)
| Endpoint | Behaviour |
|---|---|
| `POST /api/run/quick` | Demo-grade (~2 min): pop 80 · 10 generations · 1 seed · default judge rules |
| `POST /api/run/standard` | Full (~10 min): pop 200 · 30 generations · 2 seeds · all rules + clamps |

### 5. Dashboard
```powershell
# Server: serves API + production frontend build at GET /
uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir ..

# Dev: Vite proxies /api → backend
cd frontend && npm install && npm run dev
```

---

## Notes on honesty & sign-off

* Synthetic signal is calibrated to a credible fold (mean rank IC ≈ 0.115, ~80% positive) — never
  exaggerated Sharpe claims.
* Every screen carries a `DEMO DATA` / `LIVE RUN` badge so demo and live numbers are never mixed.
* The two-stage refinement path (`_stage2_mutate` → parse → `_val_ics`) was verified standalone:
  identity wrappers stripped, repairs parsed, and the IC gate passes.
