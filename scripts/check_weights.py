#!/usr/bin/env python3
"""Verify that the local LLM weight folder is present and shaped like a real
HuggingFace model, as required by the FinCAP two-stage semantic refiner.

The backend re-checks the folder on every request, so this script is a quick
pre-start sanity check. Uploading weights into the folder is enough for the
dashboard: it flips to the local LLM judge automatically (no restart).

Usage:
    python scripts/check_weights.py                 # defaults to ai_core/LLMs/Qwen-3B
    python scripts/check_weights.py --llm-dir PATH  # custom folder (must contain config.json)

Exit status: 0 when every required file is present, 1 when something is missing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LLM_DIR = REPO_ROOT / "ai_core" / "LLMs" / "Qwen-3B"

REQUIRED = {
    "model config": ["config.json"],
    "tokenizer": [
        "tokenizer.json",
        "tokenizer.model",
        "tokenizer_config.json",
    ],
    "weights": [
        "model.safetensors",
        "pytorch_model.bin",
        "model.bin",
    ],
}


def check_weights(llm_dir: Path) -> int:
    llm_dir = llm_dir.expanduser().resolve()
    print(f"LLM weight folder: {llm_dir}")
    if not llm_dir.is_dir():
        print("[MISSING] folder does not exist yet")
        print("         put the exported model (config.json + tokenizer + weights) here")
        return 1

    all_ok = True
    for label, names in REQUIRED.items():
        present = [n for n in names if (llm_dir / n).is_file()]
        missing = [n for n in names if not (llm_dir / n).is_file()]
        if present:
            print(f"  [OK]      {label:<12} found: {', '.join(present)}")
        else:
            all_ok = False
            print(f"  [MISSING] {label:<12} none of {names}")
        for name in missing:
            print(f"            - {name} is not present")

    if all_ok:
        print("ALL CHECKS PASSED - the backend will use the local LLM judge "
              "without any restart.")
        return 0
    print("SOME CHECKS FAILED - upload the missing files, then re-run this script.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--llm-dir",
        type=Path,
        default=DEFAULT_LLM_DIR,
        help="folder containing the exported LLM weights "
             "(default: ai_core/LLMs/Qwen-3B)",
    )
    args = parser.parse_args()
    return check_weights(args.llm_dir)


if __name__ == "__main__":
    sys.exit(main())
