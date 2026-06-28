"""
coords.py — metro centroid latitude/longitude for the map.

The Streamlit map plots each metro as a point, which needs coordinates. The
Census Gazetteer file gives an interior centroid (lat/lon) per CBSA, keyed by
the same CBSA code everything else uses.

No API key needed (flat zip from Census).

    .venv/Scripts/python.exe src/ingest/coords.py
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config  # noqa: E402

COORDS_RAW_DIR = config.RAW_DIR / "gazetteer"
COORDS_RAW_DIR.mkdir(parents=True, exist_ok=True)

GAZETTEER_URL = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
                 "2023_Gazetteer/2023_Gaz_cbsa_national.zip")


def fetch_coords(*, refresh: bool = False) -> pd.DataFrame:
    """Return [cbsa_code, lat, lon] for every CBSA, caching the raw file."""
    cache = COORDS_RAW_DIR / "2023_Gaz_cbsa_national.txt"
    if cache.exists() and not refresh:
        raw = pd.read_csv(cache, sep="\t", dtype=str)
    else:
        resp = requests.get(GAZETTEER_URL, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"Gazetteer download failed (status {resp.status_code}).")
        z = zipfile.ZipFile(io.BytesIO(resp.content))
        text = z.read(z.namelist()[0]).decode("latin-1")
        cache.write_text(text)
        raw = pd.read_csv(io.StringIO(text), sep="\t", dtype=str)

    raw.columns = [c.strip() for c in raw.columns]
    return pd.DataFrame({
        "cbsa_code": raw["GEOID"].str.strip(),
        "lat": pd.to_numeric(raw["INTPTLAT"], errors="coerce"),
        "lon": pd.to_numeric(raw["INTPTLONG"].str.strip(), errors="coerce"),
    }).dropna()


def build_metro_coords() -> pd.DataFrame:
    """Coords for just the frozen universe, written to data/processed/metro_coords.csv."""
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")
    universe = panel[["cbsa_code"]].drop_duplicates()
    coords = universe.merge(fetch_coords(), on="cbsa_code", how="left")
    coords.to_csv(config.PROCESSED_DIR / "metro_coords.csv", index=False)
    return coords


if __name__ == "__main__":
    c = build_metro_coords()
    print(f"metro coords: {c['lat'].notna().sum()}/{len(c)} metros located")
    print(f"  written to {(config.PROCESSED_DIR / 'metro_coords.csv').relative_to(config.ROOT)}")
