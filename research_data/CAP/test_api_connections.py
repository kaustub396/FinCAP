from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse, parse_qs


def load_env_file(env_file: Path) -> None:
    if not env_file.exists():
        raise FileNotFoundError(f".env not found at: {env_file}")
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_env(name: str, *fallbacks: str) -> str:
    for key in (name, *fallbacks):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def mask(value: str) -> str:
    if not value:
        return "MISSING"
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}***{value[-3:]}"


def generate_totp(secret: str, interval: int = 30, digits: int = 6) -> str:
    cleaned = secret.upper().replace(" ", "")
    pad_len = (-len(cleaned)) % 8
    if pad_len:
        cleaned += "=" * pad_len
    key = base64.b32decode(cleaned, casefold=True)
    counter = int(time.time() // interval)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code_int % (10**digits)).zfill(digits)


def normalize_totp_secret(raw_secret: str) -> str:
    value = raw_secret.strip().strip('"').strip("'")
    if value.startswith("otpauth://"):
        parsed = urlparse(value)
        qs = parse_qs(parsed.query)
        value = qs.get("secret", [""])[0]
    value = value.replace(" ", "").replace("-", "")
    return value


def test_fmp(api_key: str) -> tuple[bool, str]:
    try:
        url = (
            "https://financialmodelingprep.com/stable/profile?"
            + urllib.parse.urlencode({"symbol": "AAPL", "apikey": api_key})
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(payload, list) and payload:
            return True, "FMP reachable and key accepted."
        return False, f"FMP reachable but unexpected response: {str(payload)[:160]}"
    except Exception as exc:
        return False, f"FMP check failed: {exc}"


def test_smartapi(api_key: str, client_code: str, pin_or_password: str, totp_secret: str) -> tuple[bool, str]:
    try:
        from SmartApi import SmartConnect  # type: ignore
    except Exception:
        return False, "smartapi-python not installed. Install with: pip install smartapi-python"

    try:
        totp = generate_totp(normalize_totp_secret(totp_secret))
    except Exception as exc:
        return False, f"Could not generate TOTP from secret: {exc}"

    try:
        conn = SmartConnect(api_key=api_key)
        session = conn.generateSession(client_code, pin_or_password, totp)
        ok = bool(session) and str(session.get("status", "")).lower() == "true"
        if ok:
            return True, "SmartAPI login/session generation succeeded."
        return False, f"SmartAPI responded but login failed: {str(session)[:200]}"
    except Exception as exc:
        return False, f"SmartAPI check failed: {exc}"


def main() -> int:
    env_path = Path(__file__).resolve().parent / "env" / ".env"
    load_env_file(env_path)

    smartapi_api_key = get_env("SMARTAPI_API_KEY")
    smartapi_client_code = get_env("SMARTAPI_CLIENT_CODE", "SMART_API_CLIENTID")
    smartapi_pin_or_password = get_env("SMARTAPI_PIN", "SMARTAPI_PASSWORD")
    smartapi_totp_secret = get_env("SMARTAPI_TOTP_SECRET", "SMARTAPI_TOPT", "SMARTAPI_TOTP")
    fmp_api_key = get_env("FMP_API_KEY", "Fmp_api_key")

    print("=== Key Presence (masked) ===")
    print("SMARTAPI_API_KEY:", mask(smartapi_api_key))
    print("SMARTAPI_CLIENT_CODE:", mask(smartapi_client_code))
    print("SMARTAPI_PIN/PASSWORD:", mask(smartapi_pin_or_password))
    print("SMARTAPI_TOTP_SECRET:", mask(smartapi_totp_secret))
    print("FMP_API_KEY:", mask(fmp_api_key))
    print()

    all_ok = True

    if fmp_api_key:
        ok, msg = test_fmp(fmp_api_key)
        print("[FMP]", "PASS -" if ok else "FAIL -", msg)
        all_ok = all_ok and ok
    else:
        print("[FMP] FAIL - Missing FMP_API_KEY")
        all_ok = False

    if smartapi_api_key and smartapi_client_code and smartapi_pin_or_password and smartapi_totp_secret:
        ok, msg = test_smartapi(
            smartapi_api_key, smartapi_client_code, smartapi_pin_or_password, smartapi_totp_secret
        )
        print("[SmartAPI]", "PASS -" if ok else "FAIL -", msg)
        all_ok = all_ok and ok
    else:
        print("[SmartAPI] FAIL - Missing one or more required SmartAPI credentials")
        all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
