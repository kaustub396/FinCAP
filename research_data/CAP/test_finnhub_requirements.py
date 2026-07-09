from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


def load_env_file(env_file: Path) -> None:
    if not env_file.exists():
        raise FileNotFoundError(f".env not found at: {env_file}")
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def get_json(url: str, params: dict) -> tuple[int, object]:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        full_url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return code, json.loads(body)
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return exc.code, parsed


def probe_symbol_coverage(token: str) -> tuple[str | None, str | None]:
    code, payload = get_json(
        "https://finnhub.io/api/v1/search",
        {"q": "RELIANCE", "token": token},
    )
    if code != 200 or not isinstance(payload, dict):
        return None, f"search failed: HTTP {code}"

    results = payload.get("result", [])
    if not isinstance(results, list):
        return None, "search result format unexpected"

    # Prefer NSE/BSE suffixes if present
    for item in results:
        symbol = str(item.get("symbol", ""))
        if symbol.endswith(".NS") or symbol.endswith(".BO"):
            return symbol, None

    # fall back to first hit
    if results:
        return str(results[0].get("symbol", "")), None
    return None, "no matching symbol found for RELIANCE"


def main() -> int:
    env_path = Path(__file__).resolve().parent / "env" / ".env"
    load_env_file(env_path)

    token = get_env("FINNHUB_API_KEY", "FINNHUB_TOKEN", "FINHUB_API_KEY")
    if not token:
        print("[Finnhub] FAIL - Missing FINNHUB_API_KEY (or FINNHUB_TOKEN) in env/.env")
        return 1

    report: dict = {"provider": "Finnhub", "checks": {}}

    # 1) Symbol coverage check for Indian universe candidate
    symbol, err = probe_symbol_coverage(token)
    report["checks"]["symbol_lookup"] = {"ok": err is None, "symbol": symbol, "error": err}

    # 2) Profile + basic financials field availability
    test_symbol = symbol or "AAPL"

    profile_code, profile = get_json(
        "https://finnhub.io/api/v1/stock/profile2",
        {"symbol": test_symbol, "token": token},
    )
    report["checks"]["profile"] = {
        "http": profile_code,
        "ok": profile_code == 200 and isinstance(profile, dict) and bool(profile),
        "has_name": isinstance(profile, dict) and bool(profile.get("name")),
        "has_finnhub_industry": isinstance(profile, dict) and bool(profile.get("finnhubIndustry")),
    }

    basic_code, basic = get_json(
        "https://finnhub.io/api/v1/stock/metric",
        {"symbol": test_symbol, "metric": "all", "token": token},
    )
    metric = basic.get("metric", {}) if isinstance(basic, dict) else {}
    report["checks"]["basic_financials"] = {
        "http": basic_code,
        "ok": basic_code == 200 and isinstance(metric, dict) and bool(metric),
        "fields": {
            "PE": isinstance(metric, dict) and any(
                metric.get(k) is not None for k in ("peBasicExclExtraTTM", "peTTM", "peAnnual")
            ),
            "ROE": isinstance(metric, dict) and any(
                metric.get(k) is not None for k in ("roeTTM", "roeRfy", "roeAnnual")
            ),
            "Current_Ratio": isinstance(metric, dict) and any(
                metric.get(k) is not None for k in ("currentRatioAnnual", "currentRatioQuarterly")
            ),
            "Debt_Equity": isinstance(metric, dict) and any(
                metric.get(k) is not None for k in ("totalDebt/totalEquityAnnual", "totalDebt/totalEquityQuarterly")
            ),
            "ROCE": isinstance(metric, dict)
            and any(metric.get(k) is not None for k in ("roicTTM", "roiTTM", "roaTTM")),
        },
    }

    # 3) Statement availability (needed for deriving missing ratios)
    fs_code, fs = get_json(
        "https://finnhub.io/api/v1/stock/financials-reported",
        {"symbol": test_symbol, "freq": "annual", "token": token},
    )
    data_list = fs.get("data", []) if isinstance(fs, dict) else []
    report["checks"]["financials_reported"] = {
        "http": fs_code,
        "ok": fs_code == 200 and isinstance(data_list, list),
        "records_returned": len(data_list) if isinstance(data_list, list) else 0,
    }

    # 4) OHLC availability in Finnhub (to confirm premium gate behavior)
    candle_code, candles = get_json(
        "https://finnhub.io/api/v1/stock/candle",
        {
            "symbol": test_symbol,
            "resolution": "D",
            "from": 1704067200,  # 2024-01-01
            "to": 1706659200,  # 2024-01-31
            "token": token,
        },
    )
    report["checks"]["candles"] = {
        "http": candle_code,
        "ok": candle_code == 200 and isinstance(candles, dict) and candles.get("s") == "ok",
        "status_field": candles.get("s") if isinstance(candles, dict) else None,
    }

    print(json.dumps(report, indent=2))

    # success means we got enough for fundamentals pipeline
    bf = report["checks"]["basic_financials"]["fields"]
    fundamentals_ok = bool(bf["PE"] and bf["ROE"] and bf["Current_Ratio"] and bf["Debt_Equity"])
    return 0 if fundamentals_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
