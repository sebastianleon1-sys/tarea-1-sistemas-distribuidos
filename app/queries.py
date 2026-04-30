import bisect
from data import zone_data, zone_area_km2


def _records_with_confidence(zone_id: str, confidence_min: float):
    confidence_values = zone_data[zone_id]["confidence"]
    start_idx = bisect.bisect_left(confidence_values, confidence_min)

    df = zone_data[zone_id]["df"]
    return df.iloc[start_idx:]


def q1_count(zone_id: str, confidence_min: float = 0.0) -> int:
    filtered = _records_with_confidence(zone_id, confidence_min)
    return int(len(filtered))


def q2_area(zone_id: str, confidence_min: float = 0.0) -> dict:
    filtered = _records_with_confidence(zone_id, confidence_min)

    if filtered.empty:
        return {
            "avg_area": 0.0,
            "total_area": 0.0,
            "n": 0,
        }

    return {
        "avg_area": round(float(filtered["area_in_meters"].mean()), 4),
        "total_area": round(float(filtered["area_in_meters"].sum()), 4),
        "n": int(len(filtered)),
    }


def q3_density(zone_id: str, confidence_min: float = 0.0) -> float:
    count = q1_count(zone_id, confidence_min)
    area_km2 = zone_area_km2.get(zone_id, 1.0)

    return round(count / area_km2, 4)


def q4_compare(zone_a: str, zone_b: str, confidence_min: float = 0.0) -> dict:
    da = q3_density(zone_a, confidence_min)
    db = q3_density(zone_b, confidence_min)

    winner = zone_a if da >= db else zone_b

    return {
        "zone_a": {
            "id": zone_a,
            "density": da,
        },
        "zone_b": {
            "id": zone_b,
            "density": db,
        },
        "winner": winner,
    }


def q5_confidence_dist(zone_id: str, bins: int = 5) -> list[dict]:
    confidence_values = zone_data[zone_id]["confidence"]

    if len(confidence_values) == 0:
        return []

    bin_size = 1.0 / bins
    counts = [0] * bins

    for score in confidence_values:
        idx = min(int(score / bin_size), bins - 1)
        counts[idx] += 1

    result = []

    for i in range(bins):
        result.append(
            {
                "bucket": i,
                "min": round(i * bin_size, 4),
                "max": round((i + 1) * bin_size, 4),
                "count": counts[i],
            }
        )

    return result


def cache_key_q1(zone_id: str, confidence_min: float = 0.0) -> str:
    return f"count:{zone_id}:conf={confidence_min}"


def cache_key_q2(zone_id: str, confidence_min: float = 0.0) -> str:
    return f"area:{zone_id}:conf={confidence_min}"


def cache_key_q3(zone_id: str, confidence_min: float = 0.0) -> str:
    return f"density:{zone_id}:conf={confidence_min}"


def cache_key_q4(zone_a: str, zone_b: str, confidence_min: float = 0.0) -> str:
    return f"compare:density:{zone_a}:{zone_b}:conf={confidence_min}"


def cache_key_q5(zone_id: str, bins: int = 5) -> str:
    return f"confidence_dist:{zone_id}:bins={bins}"


if __name__ == "__main__":
    print("Q1 Z1:", q1_count("Z1"))
    print("Q2 Z1:", q2_area("Z1"))
    print("Q3 Z1:", q3_density("Z1"))
    print("Q4 Z1 vs Z2:", q4_compare("Z1", "Z2"))
    print("Q5 Z1:", q5_confidence_dist("Z1"))