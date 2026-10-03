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
├── .gitignore                         # Git exclusion rules for large files
├── requirements.txt                   # Environment dependencies
│
├── ai_core/                           # Core algorithmic pipeline
│   ├── gp/                            # Genetic programming engine and experiment runners
│   │   ├── gp_engine.py               # Tree representation, operators, and ICIR fitness
│   │   ├── regime_gp.py               # HMM regime routing logic
│   │   ├── final_experiments.py       # Main experiment script (GP + LLM refiner loop)
│   │   ├── evaluation.py              # Performance evaluation (Sharpe, IC, Drawdown)
│   │   └── baselines.py               # Benchmark factor implementations
│   ├── llm_refiner/                   # Two-Stage LLM Semantic Refiner
│   │   └── llm_refiner.py             # Stage 1 scoring and Stage 2 AST-constrained mutation
│   ├── regimes/                       # Market regime modeling
│   │   └── regime_detector.py         # 2-state Gaussian HMM implementation
│   ├── afm/                           # Adaptive Fusion Model
│   │   └── extract_afm_data.py        # Macro news sentiment and fundamental ratio fusion
│   └── LLMs/                          # Local model setup
│       └── LLMs.ipynb                 # Weight download and testing notebook
│
├── research_data/                     # Data acquisition and preprocessing
│   ├── download_data.py               # Raw market data extraction (Nifty 50, S&P 500, SSE)
│   ├── standardize_data.py            # Data cleaning and corporate action adjustments
│   └── build_features.py              # Technical indicator panel computation
│
├── backend/                           # Backend API services
├── frontend/                          # Web application interface
│
└── documentation/                     # Academic paper draft and diagrams
    ├── access.tex                     # IEEE Access LaTeX manuscript (12 pages)
    ├── access.pdf                     # Compiled paper PDF
    └── *.png                          # Architecture and ablation plots
```

---

## Setup and Reproduction

### 1. Environment Setup

Python 3.10 or higher is required.

```bash
git clone https://github.com/kaustub396/FinCAP.git
cd FinCAP

python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Download Model Weights

The LLM refiners run locally using open-weights models (no external API calls required). Open and run `ai_core/LLMs/LLMs.ipynb` to download the quantized weights for:
- `Qwen/Qwen2.5-3B-Instruct` (or `meta-llama/Llama-3.2-3B-Instruct`)
- `google/gemma-2-2b-it`

Model weights are saved locally under `ai_core/LLMs/` and are excluded from Git commits via `.gitignore`.

### 3. Running the Pipeline

To run the full factor discovery pipeline with the Two-Stage LLM Semantic Refinement loop:

```bash
cd "ai_core/Previous models/Hybrid-FinGpAlpha/gp"
python final_experiments.py
```

To run baseline models without LLM refinement:

```bash
python baselines.py
```

---

## Project Team

- **Raghav Anand:** AI & Quantitative Research Lead (GP Engine, Two-Stage LLM Refiner, IEEE Access manuscript)
- **Member 1:** Frontend Development Lead (Web dashboard, interactive portfolio visualization)
- **Member 2:** Backend Architecture Lead (API routing, real-time pipeline integration)
- **Member 3:** Financial Data & Research Lead (Data ingestion, preprocessing, market data validation)

---

## Research Manuscript

The research paper detailing the methodology, mathematical formulation, closed grammar specifications, and ablation analysis is available in the repository:
- Source: `documentation/ACCESS_latex_template_20240429/access.tex`
- PDF: `documentation/ACCESS_latex_template_20240429/access.pdf`
