"""Debug: inspect raw ticket data from Ticimax."""

import json

import httpx

r = httpx.get(
    "http://127.0.0.1:8000/api/support/tickets",
    params={"durum_id": -1, "kayit_sayisi": 3},
    timeout=30,
)
r.raise_for_status()
data = r.json()
print(json.dumps(data, indent=2, ensure_ascii=False, default=str)[:3000])
