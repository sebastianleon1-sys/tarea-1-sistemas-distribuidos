import os
import math
import pandas as pd

ZONES = {
    "Z1": {"name": "Providencia",     "lat_min": -33.445, "lat_max": -33.420, "lon_min": -70.640, "lon_max": -70.600},
    "Z2": {"name": "Las Condes",      "lat_min": -33.420, "lat_max": -33.390, "lon_min": -70.600, "lon_max": -70.550},
    "Z3": {"name": "Maipú",           "lat_min": -33.530, "lat_max": -33.490, "lon_min": -70.790, "lon_max": -70.740},
    "Z4": {"name": "Santiago Centro", "lat_min": -33.460, "lat_max": -33.430, "lon_min": -70.670, "lon_max": -70.630},
    "Z5": {"name": "Pudahuel",        "lat_min": -33.470, "lat_max": -33.430, "lon_min": -70.810, "lon_max": -70.760},
}

BASE_DIR = os.path.dirname(__file__)
ORIGINAL_DATA_PATH = os.path.join(BASE_DIR, "data", "967_buildings.csv.gz")


def _bbox_area_km2(zone_id: str) -> float:
    z = ZONES[zone_id]

    lat_center = (z["lat_min"] + z["lat_max"]) / 2
    delta_lat_km = (z["lat_max"] - z["lat_min"]) * 111.0
    delta_lon_km = (
        (z["lon_max"] - z["lon_min"])
        * 111.0
        * math.cos(math.radians(lat_center))
    )

    return abs(delta_lat_km * delta_lon_km)


def _load_full_dataset_and_filter_zones() -> dict:
    print(f"\n[Data] Cargando dataset completo: {ORIGINAL_DATA_PATH}")

    if not os.path.exists(ORIGINAL_DATA_PATH):
        raise FileNotFoundError(
            f"No se encontró {ORIGINAL_DATA_PATH}. "
            "Copia 967_buildings.csv.gz dentro de app/data/"
        )

    df = pd.read_csv(
        ORIGINAL_DATA_PATH,
        usecols=["latitude", "longitude", "area_in_meters", "confidence"],
        compression="gzip",
        low_memory=False,
    )

    print(f"[Data] Dataset completo leído: {len(df):,} edificios")
    print("[Data] Filtrando y precargando zonas en memoria...")

    result = {}

    for zone_id, z in ZONES.items():
        zone_df = df[
            (df["latitude"] >= z["lat_min"]) &
            (df["latitude"] <= z["lat_max"]) &
            (df["longitude"] >= z["lon_min"]) &
            (df["longitude"] <= z["lon_max"])
        ].copy()

        zone_df = zone_df.sort_values("confidence").reset_index(drop=True)

        result[zone_id] = {
            "df": zone_df,
            "confidence": zone_df["confidence"],
            "area": zone_df["area_in_meters"],
        }

        print(
            f"  [OK] {zone_id} ({z['name']}): "
            f"{len(zone_df):,} edificios cargados"
        )

    del df

    return result


zone_data = _load_full_dataset_and_filter_zones()
zone_area_km2 = {zone_id: _bbox_area_km2(zone_id) for zone_id in ZONES}


if __name__ == "__main__":
    print("\n=== Resumen por zona ===")

    for zone_id, z in ZONES.items():
        n = len(zone_data[zone_id]["df"])
        area = zone_area_km2[zone_id]

        print(
            f"{zone_id} ({z['name']}): "
            f"{n:,} edificios | {area:.2f} km²"
        )