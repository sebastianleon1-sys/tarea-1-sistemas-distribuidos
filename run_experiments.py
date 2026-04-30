#!/usr/bin/env python3

import subprocess
import json
import time
import os
import re
import sys
import itertools

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


POLICIES = {
    "LRU": "allkeys-lru",
    "LFU": "allkeys-lfu",

    # Redis no tiene FIFO puro.
    # Como todas las keys tienen TTL fijo, volatile-ttl se aproxima a FIFO:
    # las keys más antiguas tienen menos TTL restante y se expulsan primero.
    "FIFO": "volatile-ttl",
}

SIZES = ["50mb", "200mb", "500mb"]
DISTRIBUTIONS = ["zipf", "uniform"]

N_QUERIES = 10000
FIXED_TTL = 300
SEED = 42

OUTPUT_DIR = "experiment_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def stop_all():
    subprocess.run(
        ["docker", "compose", "down", "-v"],
        capture_output=True,
        text=True,
    )
    time.sleep(2)


def patch_compose(policy_raw, size):
    with open("docker-compose.yml", "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(
        r"--maxmemory-policy \S+",
        f"--maxmemory-policy {policy_raw}",
        content,
    )

    content = re.sub(
        r"--maxmemory \S+",
        f"--maxmemory {size}",
        content,
    )

    with open("docker-compose.yml", "w", encoding="utf-8") as f:
        f.write(content)


def start_redis():
    subprocess.run(
        ["docker", "compose", "up", "-d", "redis"],
        capture_output=True,
        text=True,
    )

    for _ in range(20):
        result = subprocess.run(
            ["docker", "exec", "redis_cache", "redis-cli", "ping"],
            capture_output=True,
            text=True,
        )

        if "PONG" in result.stdout:
            return

        time.sleep(1)

    raise RuntimeError("Redis no respondió con PONG.")


def run_app(distribution):
    result = subprocess.run(
        [
            "docker",
            "compose",
            "run",
            "--rm",
            "app",
            "python",
            "main.py",
            "--distribution",
            distribution,
            "--queries",
            str(N_QUERIES),
            "--ttl",
            str(FIXED_TTL),
            "--seed",
            str(SEED),
        ],
        capture_output=True,
        text=True,
    )

    print(result.stdout)

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"Falló app con distribución {distribution}")

    return parse_stdout(result.stdout, distribution)


def parse_stdout(stdout, distribution):
    metrics = {"distribution": distribution}

    patterns = [
        ("hit_rate", r"Hit rate\s*:\s*([\d.]+)%", lambda x: float(x) / 100),
        ("miss_rate", r"Miss rate\s*:\s*([\d.]+)%", lambda x: float(x) / 100),
        ("throughput_qps", r"Throughput\s*:\s*([\d.]+)", float),
        ("latency_p50_ms", r"Latencia p50\s*:\s*([\d.]+)", float),
        ("latency_p95_ms", r"Latencia p95\s*:\s*([\d.]+)", float),
        ("eviction_rate_pm", r"Eviction rate\s*:\s*([\d.]+)", float),
        ("cache_efficiency", r"Cache efficiency\s*:\s*(-?[\d.]+)", float),
    ]

    for key, pattern, fn in patterns:
        match = re.search(pattern, stdout)

        if match:
            metrics[key] = fn(match.group(1))

    memory_match = re.search(
        r"\[Redis\] used_memory=([^\s]+)\s+\|\s+maxmemory=([^\s]+)",
        stdout,
    )

    if memory_match:
        metrics["used_memory_human"] = memory_match.group(1)
        metrics["maxmemory_human"] = memory_match.group(2)

    by_type = {}

    for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
        match = re.search(rf"{q}: hits=(\d+), misses=(\d+)", stdout)

        if match:
            hits = int(match.group(1))
            misses = int(match.group(2))
            total = hits + misses

            by_type[q] = {
                "hits": hits,
                "misses": misses,
                "hit_rate": hits / total if total > 0 else 0,
            }

    metrics["by_query_type"] = by_type

    return metrics


def run_all():
    combos = list(itertools.product(POLICIES.items(), SIZES, DISTRIBUTIONS))
    all_results = []

    print(f"\n{'=' * 60}")
    print(f"  {len(combos)} experimentos ({N_QUERIES} consultas c/u)")
    print(f"  TTL fijo: {FIXED_TTL}s | Seed: {SEED}")
    print(f"{'=' * 60}\n")

    for i, ((policy_name, policy_raw), size, distribution) in enumerate(combos, 1):
        print(
            f"[{i:2d}/{len(combos)}] "
            f"{policy_name} / {size} / {distribution} ...",
            flush=True,
        )

        stop_all()
        patch_compose(policy_raw, size)
        start_redis()

        subprocess.run(
            ["docker", "exec", "redis_cache", "redis-cli", "flushall"],
            capture_output=True,
            text=True,
        )

        metrics = run_app(distribution)

        metrics.update(
            {
                "policy": policy_name,
                "policy_raw": policy_raw,
                "size": size,
                "distribution": distribution,
                "n_queries": N_QUERIES,
                "ttl": FIXED_TTL,
                "seed": SEED,
            }
        )

        all_results.append(metrics)

        print(
            f"RESUMEN => "
            f"hit_rate={metrics.get('hit_rate', 0) * 100:.1f}% | "
            f"evictions/min={metrics.get('eviction_rate_pm', 0):.1f} | "
            f"used_memory={metrics.get('used_memory_human', 'N/A')}\n"
        )

        filename = f"{policy_name}_{size}_{distribution}.json"
        path = os.path.join(OUTPUT_DIR, filename)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

    all_path = os.path.join(OUTPUT_DIR, "all_results.json")

    with open(all_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    stop_all()
    patch_compose("allkeys-lru", "200mb")

    print(f"\n✓ Resultados guardados en ./{OUTPUT_DIR}/\n")

    return all_results


def get(results, **filters):
    selected = results

    for key, value in filters.items():
        selected = [r for r in selected if r.get(key) == value]

    return selected


def save(fig, name):
    fig.savefig(
        os.path.join(OUTPUT_DIR, name),
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(fig)
    print(f"  ✓ {name}")


def generate_plots(results):
    print("[Plots] Generando gráficos...\n")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    for ax, distribution in zip(axes, DISTRIBUTIONS):
        selected = get(results, size="50mb", distribution=distribution)

        ax.bar(
            [r["policy"] for r in selected],
            [r.get("hit_rate", 0) * 100 for r in selected],
        )

        ax.set_title(f"Hit Rate por Política\n({distribution.capitalize()}, 50 MB)")
        ax.set_ylabel("Hit Rate (%)")
        ax.set_ylim(0, 100)

    fig.suptitle("Impacto de la Política de Evicción", fontweight="bold")
    plt.tight_layout()
    save(fig, "01_hit_rate_por_politica.png")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    for ax, distribution in zip(axes, DISTRIBUTIONS):
        selected = get(results, policy="LRU", distribution=distribution)

        ax.bar(
            [r["size"] for r in selected],
            [r.get("hit_rate", 0) * 100 for r in selected],
        )

        ax.set_title(f"Hit Rate por Tamaño\n(LRU, {distribution.capitalize()})")
        ax.set_ylabel("Hit Rate (%)")
        ax.set_ylim(0, 100)

    fig.suptitle("Impacto del Tamaño de Caché", fontweight="bold")
    plt.tight_layout()
    save(fig, "02_hit_rate_por_tamano.png")

    fig, ax = plt.subplots(figsize=(7, 5))
    selected = get(results, policy="LRU", size="50mb")

    ax.bar(
        [r["distribution"].capitalize() for r in selected],
        [r.get("hit_rate", 0) * 100 for r in selected],
        width=0.4,
    )

    ax.set_title("Zipf vs Uniforme — Hit Rate\n(LRU, 50 MB)")
    ax.set_ylabel("Hit Rate (%)")
    ax.set_ylim(0, 100)

    plt.tight_layout()
    save(fig, "03_zipf_vs_uniform.png")

    fig, ax = plt.subplots(figsize=(9, 5))
    selected = get(results, size="50mb", distribution="zipf")

    x = list(range(len(selected)))
    width = 0.35

    ax.bar(
        [i - width / 2 for i in x],
        [r.get("latency_p50_ms", 0) for r in selected],
        width,
        label="p50",
    )

    ax.bar(
        [i + width / 2 for i in x],
        [r.get("latency_p95_ms", 0) for r in selected],
        width,
        label="p95",
    )

    ax.set_xticks(x)
    ax.set_xticklabels([r["policy"] for r in selected])
    ax.set_title("Latencia p50 y p95 por Política\n(Zipf, 50 MB)")
    ax.set_ylabel("Latencia (ms)")
    ax.legend()

    plt.tight_layout()
    save(fig, "04_latencias.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    selected = get(results, policy="LRU", distribution="zipf")

    ax.bar(
        [r["size"] for r in selected],
        [r.get("eviction_rate_pm", 0) for r in selected],
    )

    ax.set_title("Eviction Rate por Tamaño\n(LRU, Zipf)")
    ax.set_ylabel("Evictions / minuto")

    plt.tight_layout()
    save(fig, "05_eviction_rate.png")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    for ax, distribution in zip(axes, DISTRIBUTIONS):
        selected = get(
            results,
            policy="LRU",
            size="50mb",
            distribution=distribution,
        )

        if selected:
            by_type = selected[0].get("by_query_type", {})
            query_types = sorted(by_type.keys())

            ax.bar(
                query_types,
                [by_type[q].get("hit_rate", 0) * 100 for q in query_types],
            )

            ax.set_title(
                f"Hit Rate por Tipo de Consulta\n"
                f"(LRU, 50 MB, {distribution.capitalize()})"
            )
            ax.set_ylabel("Hit Rate (%)")
            ax.set_ylim(0, 100)

    fig.suptitle("Desempeño por Tipo de Consulta Q1-Q5", fontweight="bold")
    plt.tight_layout()
    save(fig, "06_hit_rate_por_query.png")

    print(f"\n✓ 6 gráficos guardados en ./{OUTPUT_DIR}/")


if __name__ == "__main__":
    if "--plots-only" in sys.argv:
        with open(
            os.path.join(OUTPUT_DIR, "all_results.json"),
            "r",
            encoding="utf-8",
        ) as f:
            results = json.load(f)

        generate_plots(results)
    else:
        results = run_all()
        generate_plots(results)