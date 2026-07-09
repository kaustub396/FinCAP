"""Test IndianAPI with different auth methods."""
import os, re, requests, json
from pathlib import Path

text = Path(r"C:\Users\EV-Car\CAP\env\.env").read_text(encoding="utf-8")
m = re.search(r"^INDIANAPI_API_KEY\s*=\s*(.+)$", text, re.M)
api_key = m.group(1).strip().strip('"').strip("'")
print(f"Key (masked): {api_key[:6]}***{api_key[-4:]}")
print(f"Key length: {len(api_key)}")
print()

base_url = "https://analyst.indianapi.in"
test_url = f"{base_url}/stock"
params = {"name": "RELIANCE"}

# Method 1: X-API-Key header
print("Method 1: X-API-Key header")
r = requests.get(test_url, params=params, headers={"X-API-Key": api_key}, timeout=15)
print(f"  Status: {r.status_code} | {r.text[:200]}")
print()

# Method 2: x-api-key header (lowercase)
print("Method 2: x-api-key header (lowercase)")
r = requests.get(test_url, params=params, headers={"x-api-key": api_key}, timeout=15)
print(f"  Status: {r.status_code} | {r.text[:200]}")
print()

# Method 3: Authorization Bearer
print("Method 3: Authorization: Bearer")
r = requests.get(test_url, params=params, headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
print(f"  Status: {r.status_code} | {r.text[:200]}")
print()

# Method 4: API key as query param
print("Method 4: api_key query param")
r = requests.get(test_url, params={**params, "api_key": api_key}, timeout=15)
print(f"  Status: {r.status_code} | {r.text[:200]}")
print()

# Method 5: X-Api-Key (mixed case)
print("Method 5: X-Api-Key (mixed case)")
r = requests.get(test_url, params=params, headers={"X-Api-Key": api_key}, timeout=15)
print(f"  Status: {r.status_code} | {r.text[:200]}")
print()

# Method 6: apiKey query param
print("Method 6: apiKey query param")
r = requests.get(test_url, params={**params, "apiKey": api_key}, timeout=15)
print(f"  Status: {r.status_code} | {r.text[:200]}")
