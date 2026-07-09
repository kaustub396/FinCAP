from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests


def load_env_file(env_file: Path) -> None:
    if not env_file.exists():
        raise FileNotFoundError(f".env not found at: {env_file}")
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_env(*names: str) -> tuple[str, str]:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    return "", ""


def extract_token(raw_value: str) -> str:
    value = raw_value.strip().strip('"').strip("'")
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        qs = parse_qs(parsed.query)
        token = qs.get("token", [""])[0]
        return token.strip()
    return value


def main() -> int:
    env_path = Path(__file__).resolve().parent / "env" / ".env"
    load_env_file(env_path)

    token, token_name = get_env(
        "APIFY_API_TOKEN",
        "APIFY_TOKEN",
        "APIFY_KEY",
        "APIFY_GET_RUN_TOKEN",
        "APIFY_GET_RUN_API_KEY",
        "APIFY_GET_DATASETITEMS_API_KEY",
        "APIFY_GET_LOG_API_KEY",
    )
    token = extract_token(token)

    if not token:
        print(
            json.dumps(
                {
                    "provider": "Apify",
                    "error": "Missing token in .env (try APIFY_API_TOKEN or APIFY_GET_RUN_API_KEY)",
                },
                indent=2,
            )
        )
        return 1

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    out: dict = {"provider": "Apify", "token_var_used": token_name, "checks": {}}

    # 1) Basic auth check
    me = requests.get("https://api.apify.com/v2/users/me", headers=headers, timeout=30)
    out["checks"]["users_me"] = {
        "http": me.status_code,
        "ok": me.status_code == 200,
    }

    if me.status_code == 200:
        data = me.json().get("data", {})
        out["checks"]["users_me"]["username"] = data.get("username")
        out["checks"]["users_me"]["email_present"] = bool(data.get("email"))
    else:
        out["checks"]["users_me"]["message"] = me.text[:200]

    # 2) Read actor list permission
    acts = requests.get(
        "https://api.apify.com/v2/acts",
        headers=headers,
        params={"limit": 3},
        timeout=30,
    )
    out["checks"]["list_acts"] = {
        "http": acts.status_code,
        "ok": acts.status_code == 200,
    }
    if acts.status_code == 200:
        items = acts.json().get("data", {}).get("items", [])
        out["checks"]["list_acts"]["count_sample"] = len(items)
        out["checks"]["list_acts"]["sample_ids"] = [x.get("id") for x in items[:3]]
    else:
        out["checks"]["list_acts"]["message"] = acts.text[:200]

    # 3) Read run list permission
    runs = requests.get(
        "https://api.apify.com/v2/actor-runs",
        headers=headers,
        params={"limit": 3},
        timeout=30,
    )
    out["checks"]["list_runs"] = {
        "http": runs.status_code,
        "ok": runs.status_code == 200,
    }
    if runs.status_code == 200:
        items = runs.json().get("data", {}).get("items", [])
        out["checks"]["list_runs"]["count_sample"] = len(items)
        out["checks"]["list_runs"]["statuses"] = [x.get("status") for x in items[:3]]
    else:
        out["checks"]["list_runs"]["message"] = runs.text[:200]

    print(json.dumps(out, indent=2))

    all_ok = (
        out["checks"]["users_me"]["ok"]
        and out["checks"]["list_acts"]["ok"]
        and out["checks"]["list_runs"]["ok"]
    )
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
