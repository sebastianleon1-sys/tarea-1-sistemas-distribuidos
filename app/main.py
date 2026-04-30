import argparse
import os
import time

from cache import handle_query, flush_cache, cache_info
from metrics import MetricsStore
from traffic_generator import generate_batch
from queries import (
    q1_count,
    q2_area,
    q3_density,
    q4_compare,
    q5_confidence_dist,
)


def build_compute_fn(query):
    qt = query.query_type
    z = query.zone_id
    c = query.confidence_min

    if qt == "Q1":
        return lambda: q1_count(z, c)

    if qt == "Q2":
        return lambda: q2_area(z, c)

    if qt == "Q3":
        return lambda: q3_density(z, c)

    if qt == "Q4":
        return lambda: q4_compare(z, query.zone_b, c)

    if qt == "Q5":
        return lambda: q5_confidence_dist(z, query.bins)

    return lambda: {"error": f"Tipo de consulta desconocido: {qt}"}


TTL_BY_QUERY = {
    "Q1": 60,
    "Q2": 60,
    "Q3": 120,
    "Q4": 120,
    "Q5": 90,
}


def run_simulation(
    distribution: str = "zipf",
    n_queries: int = 10000,
    ttl: int | None = None,
    verbose: bool = False,
    flush: bool = True,
    seed: int | None = None,
):
    print(f"\n{'=' * 55}")
    print(f"  SIMULACIÓN: distribución={distribution}, n={n_queries}, seed={seed}")
    print(f"{'=' * 55}")

    if flush:
        flush_cache()
        print("[Cache] Caché limpiado.\n")

    metrics = MetricsStore()

    queries = generate_batch(n_queries, distribution, seed=seed)

    start_wall = time.time()

    for i, query in enumerate(queries):
        key = query.cache_key()
        compute_fn = build_compute_fn(query)
        query_ttl = ttl if ttl is not None else TTL_BY_QUERY.get(query.query_type, 60)

        result, hit, latency_ms = handle_query(
            key,
            compute_fn,
            metrics,
            ttl=query_ttl,
        )

        if verbose:
            status = "HIT " if hit else "MISS"
            print(f"  [{i + 1:5d}] {status} | {key:<60} | {latency_ms:.2f} ms")

    elapsed_wall = time.time() - start_wall
    elapsed_min = elapsed_wall / 60.0

    redis_stats = cache_info()
    redis_evictions = redis_stats.get("evicted_keys", 0)

    print(
        f"[Redis] used_memory={redis_stats.get('used_memory_human')} | "
        f"maxmemory={redis_stats.get('maxmemory_human')}"
    )

    metrics.print_report(
        redis_evictions=redis_evictions,
        elapsed_minutes=max(elapsed_min, 1 / 60),
    )

    output_dir = "/app/output"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"metrics_{distribution}.json")
    metrics.save_to_file(output_path)

    return metrics.report(redis_evictions, elapsed_min)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sistema de caché — Tarea 1 SD 2026-1"
    )

    parser.add_argument(
        "--distribution",
        choices=["zipf", "uniform", "both"],
        default="both",
        help="Distribución de tráfico",
    )

    parser.add_argument(
        "--queries",
        type=int,
        default=10000,
        help="Número de consultas por simulación",
    )

    parser.add_argument(
        "--ttl",
        type=int,
        default=None,
        help="TTL fijo en segundos",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Imprimir cada consulta en tiempo real",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed para generar tráfico reproducible",
    )

    args = parser.parse_args()

    if args.distribution in ("zipf", "both"):
        run_simulation(
            distribution="zipf",
            n_queries=args.queries,
            ttl=args.ttl,
            verbose=args.verbose,
            seed=args.seed,
        )

    if args.distribution in ("uniform", "both"):
        run_simulation(
            distribution="uniform",
            n_queries=args.queries,
            ttl=args.ttl,
            verbose=args.verbose,
            seed=args.seed,
        )

    print("\n✓ Simulación completada. Revisa la carpeta output/.")