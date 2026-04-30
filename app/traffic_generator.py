import random
from dataclasses import dataclass
from typing import Literal

ZONE_IDS = ["Z4", "Z1", "Z2", "Z3", "Z5"]
QUERY_TYPES = ["Q1", "Q2", "Q3", "Q4", "Q5"]

# Antes tenías muy pocos valores.
# Ahora hay más variedad, pero sin volver el sistema eterno.
CONFIDENCE_VALUES = [round(i / 100, 2) for i in range(0, 101)]

# No usar 500 porque Q5 se vuelve demasiado pesada.
BIN_VALUES = list(range(2, 51))


@dataclass
class Query:
    query_type: str
    zone_id: str
    zone_b: str
    confidence_min: float
    bins: int

    def cache_key(self) -> str:
        if self.query_type == "Q1":
            return f"count:{self.zone_id}:conf={self.confidence_min}"

        if self.query_type == "Q2":
            return f"area:{self.zone_id}:conf={self.confidence_min}"

        if self.query_type == "Q3":
            return f"density:{self.zone_id}:conf={self.confidence_min}"

        if self.query_type == "Q4":
            return f"compare:density:{self.zone_id}:{self.zone_b}:conf={self.confidence_min}"

        if self.query_type == "Q5":
            return f"confidence_dist:{self.zone_id}:bins={self.bins}"

        return "unknown"

    def __repr__(self):
        return f"Query({self.query_type}, key={self.cache_key()})"


def _zipf_zone_weights(n: int, s: float = 1.2) -> list[float]:
    weights = [1.0 / (i + 1) ** s for i in range(n)]
    total = sum(weights)
    return [w / total for w in weights]


def _zipf_query_weights(n: int, s: float = 0.8) -> list[float]:
    weights = [1.0 / (i + 1) ** s for i in range(n)]
    total = sum(weights)
    return [w / total for w in weights]


def generate_query(
    distribution: Literal["zipf", "uniform"],
    rng: random.Random = None,
) -> Query:
    if rng is None:
        rng = random

    if distribution == "zipf":
        zone_id = rng.choices(
            ZONE_IDS,
            weights=_zipf_zone_weights(len(ZONE_IDS)),
            k=1,
        )[0]

        query_type = rng.choices(
            QUERY_TYPES,
            weights=_zipf_query_weights(len(QUERY_TYPES)),
            k=1,
        )[0]

    else:
        zone_id = rng.choice(ZONE_IDS)
        query_type = rng.choice(QUERY_TYPES)

    other_zones = [z for z in ZONE_IDS if z != zone_id]
    zone_b = rng.choice(other_zones)

    confidence_min = rng.choice(CONFIDENCE_VALUES)
    bins = rng.choice(BIN_VALUES)

    return Query(
        query_type=query_type,
        zone_id=zone_id,
        zone_b=zone_b,
        confidence_min=confidence_min,
        bins=bins,
    )


def generate_batch(
    n: int,
    distribution: Literal["zipf", "uniform"],
    seed: int = None,
) -> list[Query]:
    rng = random.Random(seed)
    return [generate_query(distribution, rng) for _ in range(n)]


if __name__ == "__main__":
    from collections import Counter

    print("=== Muestra Zipf ===")
    batch_zipf = generate_batch(10, "zipf", seed=0)

    for q in batch_zipf:
        print(q)

    print("\n=== Muestra Uniforme ===")
    batch_uniform = generate_batch(10, "uniform", seed=0)

    for q in batch_uniform:
        print(q)

    big_batch = generate_batch(10000, "zipf", seed=42)

    print("\n=== Distribución Zipf n=10000 ===")
    print("Por zona:", Counter(q.zone_id for q in big_batch))
    print("Por tipo:", Counter(q.query_type for q in big_batch))
    print("Keys únicas:", len(set(q.cache_key() for q in big_batch)))