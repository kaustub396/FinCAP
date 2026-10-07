"""Central configuration and path resolution for the FinCAP backend."""
from __future__ import annotations

import os
from pathlib import Path

# Repository root (backend/app/config.py -> parents[2])
ROOT = Path(__file__).resolve().parents[2]

BACKEND_DIR = ROOT / "backend"
AI_CORE_DIR = ROOT / "ai_core"
RESEARCH_DIR = ROOT / "research_data"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Real data locations (may be absent — gitignored datasets)
PROCESSED_DIR = RESEARCH_DIR / "processed"
PANEL_PATH = PROCESSED_DIR / "integrated_panel.pkl"
INDEX_PATH = PROCESSED_DIR / "NIFTY50_INDEX.csv"

# Fundamentals CSV produced by research_data/scripts/cap_data_pipeline.py
COVERAGE_CSV = RESEARCH_DIR / "scripts" / "output" / "nifty_banknifty_ratios.csv"

# Local LLM weights (downloaded via ai_core/LLMs/LLMs.ipynb, gitignored).
# Override the search folder with FINCAP_LLM_DIR=PATH (handy if you mount
# weights on another drive). Default: ai_core/LLMs/Qwen-3B
LLM_DIR_ENV = os.environ.get("FINCAP_LLM_DIR")

if LLM_DIR_ENV:
    LLM_DIR = Path(LLM_DIR_ENV).expanduser().resolve()
else:
    LLM_DIR = AI_CORE_DIR / "LLMs" / "Qwen-3B"


def llm_available() -> bool:
    """True when a usable LLM weight folder is detected *at request time*.

    The check runs on every /api/health call and on every pipeline start, so
    uploading weights (or dropping them in a custom FINCAP_LLM_DIR) needs no
    restart: the LLM judge switches over automatically.
    """
    return (LLM_DIR / "config.json").exists()


HOST = os.environ.get("FINCAP_HOST", "127.0.0.1")
PORT = int(os.environ.get("FINCAP_PORT", "8000"))

# GP run sizes: quick is the demo default, standard is the serious run
RUN_MODES = {
    "quick": dict(pop_size=80, n_gen=10, n_seeds=1, max_depth=5),
    "standard": dict(pop_size=200, n_gen=30, n_seeds=2, max_depth=6),
}
