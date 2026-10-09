"""Verify the configured Copernicus Data Space Ecosystem credentials work
end-to-end: OAuth client_credentials token + one real Sentinel-2 L2A
statistics request over a small area of interest.

Run from backend/:

    & python scripts/verify_sentinel_credentials.py

Uses SENTINEL_CLIENT_ID / SENTINEL_CLIENT_SECRET from the environment (or
backend/.env). Never prints the credentials or the access token.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
)
STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

# Matches app/satellite/sentinel_hub.py (NDVI evalscript + degree-unit res).
EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B02", "B03", "B04", "B08", "SCL", "dataMask"] }],
    output: [{ id: "ndvi", bands: 1, sampleType: "FLOAT32" }, { id: "dataMask", bands: 1 }]
  };
}
function evaluatePixel(sample) {
  var cloudy = [3, 8, 9, 10].indexOf(sample.SCL) !== -1;
  var mask = (sample.dataMask === 1 && !cloudy) ? 1 : 0;
  var denom = sample.B08 + sample.B04;
  var ndvi = denom === 0 ? 0 : (sample.B08 - sample.B04) / denom;
  return { ndvi: [ndvi], dataMask: [mask] };
}
"""


def load_credentials() -> dict[str, str]:
    client_id = os.environ.get("SENTINEL_CLIENT_ID")
    client_secret = os.environ.get("SENTINEL_CLIENT_SECRET")
    if client_id and client_secret:
        return {"client_id": client_id, "client_secret": client_secret}

    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        values: dict[str, str] = {}
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
        if values.get("SENTINEL_CLIENT_ID") and values.get("SENTINEL_CLIENT_SECRET"):
            return {
                "client_id": values["SENTINEL_CLIENT_ID"],
                "client_secret": values["SENTINEL_CLIENT_SECRET"],
            }

    sys.exit("SENTINEL_CLIENT_ID / SENTINEL_CLIENT_SECRET not set (env or backend/.env).")


def get_access_token(client: httpx.Client, client_id: str, client_secret: str) -> str:
    response = client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    if response.status_code != 200:
        sys.exit(f"OAuth token request failed: {response.status_code} {response.text}")
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        sys.exit("OAuth token response contained no access_token.")
    return str(token)


def main() -> None:
    creds = load_credentials()
    client_id, client_secret = creds["client_id"], creds["client_secret"]
    print(f"Verifying credentials for client_id prefix {client_id[:12]}...")

    with httpx.Client(timeout=45.0) as client:
        token = get_access_token(client, client_id, client_secret)
        print("[1/2] OAuth client_credentials token: OK")

        # Small real area over farmland near Nairobi; 2 km radius keeps the
        # request cheap while still exercising the full stats path.
        latitude, longitude, radius_km = -1.2921, 36.8219, 2.0
        import math
        from datetime import UTC, datetime, timedelta

        meridional_m = 111320.0
        res_deg = 10.0 / meridional_m
        resx = res_deg / max(math.cos(math.radians(latitude)), 0.01)
        lat_delta = radius_km / 111.32
        lon_delta = radius_km / (111.32 * max(math.cos(math.radians(latitude)), 0.01))
        now = datetime.now(UTC)
        start = now - timedelta(days=30)
        body = {
            "input": {
                "bounds": {
                    "bbox": [
                        longitude - lon_delta,
                        latitude - lat_delta,
                        longitude + lon_delta,
                        latitude + lat_delta,
                    ],
                    "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
                },
                "data": [{"type": "sentinel-2-l2a", "dataFilter": {"maxCloudCoverage": 60}}],
            },
            "aggregation": {
                "timeRange": {
                    "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                "aggregationInterval": {"of": "P1D"},
                "evalscript": EVALSCRIPT,
                "resx": resx,
                "resy": res_deg,
            },
        }
        stats = client.post(
            STATS_URL,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
        if stats.status_code != 200:
            sys.exit(f"[2/2] Statistics request failed: {stats.status_code} {stats.text}")
        payload = stats.json()
        entries = payload.get("data", [])
        if not entries:
            sys.exit("[2/2] Statistics request succeeded but returned no intervals.")

        print(f"[2/2] Sentinel-2 L2A statistics over {latitude},{longitude} (r={radius_km}km): OK")
        for entry in entries:
            ndvi = (
                entry.get("outputs", {})
                .get("ndvi", {})
                .get("bands", {})
                .get("B0", {})
                .get("stats", {})
            )
            sample_count = ndvi.get("sampleCount", 0)
            if sample_count <= 0:
                continue
            print(
                f"  {entry['interval']['to']}  mean NDVI {float(ndvi['mean']):.4f}  "
                f"pixels {sample_count}"
            )
        print("PASS: credentials authenticate and serve Sentinel-2 data.")


if __name__ == "__main__":
    main()
