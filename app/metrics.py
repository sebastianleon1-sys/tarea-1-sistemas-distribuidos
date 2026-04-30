"""
metrics.py — Almacenamiento y reporte de métricas del sistema.

Registra todos los eventos: hits, misses, latencias, throughput y tasa de evicción.
Métricas definidas en el enunciado:
  - Hit rate          = hits / (hits + misses)
  - Throughput        = consultas exitosas / segundo
  - Latencia p50/p95  = percentiles de tiempo de respuesta
  - Eviction rate     = evictions / minuto  (leído desde Redis)
  - Cache efficiency  = hits*t_cache - misses*t_db / total
"""

import time
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List


@dataclass
class QueryEvent:
    key:        str
    hit:        bool
    latency_ms: float
    timestamp:  float = field(default_factory=time.time)


class MetricsStore:
    def __init__(self):
        self.events: List[QueryEvent] = []
        self.start_time: float = time.time()

        # Contadores rápidos
        self._hits   = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Registro de eventos
    # ------------------------------------------------------------------
    def record_hit(self, key: str, latency_ms: float):
        self.events.append(QueryEvent(key=key, hit=True, latency_ms=latency_ms))
        self._hits += 1

    def record_miss(self, key: str, latency_ms: float):
        self.events.append(QueryEvent(key=key, hit=False, latency_ms=latency_ms))
        self._misses += 1

    # ------------------------------------------------------------------
    # Métricas calculadas
    # ------------------------------------------------------------------
    @property
    def total(self) -> int:
        return self._hits + self._misses

    @property
    def hit_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self._hits / self.total

    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate

    @property
    def throughput(self) -> float:
        """Consultas totales por segundo desde el inicio."""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        return self.total / elapsed

    def latency_percentile(self, p: float) -> float:
        """
        Retorna el percentil p (0–100) de latencia en ms.
        Ej: latency_percentile(50) → mediana, latency_percentile(95) → p95
        """
        if not self.events:
            return 0.0
        latencies = sorted(e.latency_ms for e in self.events)
        idx = int(len(latencies) * p / 100)
        idx = min(idx, len(latencies) - 1)
        return latencies[idx]

    def cache_efficiency(self, t_cache_ms: float = 1.0, t_db_ms: float = 100.0) -> float:
        """
        Cache efficiency = (hits * t_cache - misses * t_db) / total
        Valores por defecto: t_cache=1ms, t_db=100ms (simulación).
        """
        if self.total == 0:
            return 0.0
        return (self._hits * t_cache_ms - self._misses * t_db_ms) / self.total

    def hits_by_query_type(self) -> dict:
        """Desglose de hits/misses por tipo de consulta (Q1–Q5)."""
        breakdown = defaultdict(lambda: {"hits": 0, "misses": 0})
        for e in self.events:
            # Extraer tipo desde la key: "count:Z1:conf=0.0" → Q1
            prefix = e.key.split(":")[0]
            q_type = {
                "count":            "Q1",
                "area":             "Q2",
                "density":          "Q3",
                "compare":          "Q4",
                "confidence_dist":  "Q5",
            }.get(prefix, "unknown")
            if e.hit:
                breakdown[q_type]["hits"] += 1
            else:
                breakdown[q_type]["misses"] += 1
        return dict(breakdown)

    # ------------------------------------------------------------------
    # Reporte
    # ------------------------------------------------------------------
    def report(self, redis_evictions: int = 0, elapsed_minutes: float = 1.0) -> dict:
        """Genera un reporte completo de métricas."""
        eviction_rate = redis_evictions / elapsed_minutes if elapsed_minutes > 0 else 0

        return {
            "total_queries":    self.total,
            "hits":             self._hits,
            "misses":           self._misses,
            "hit_rate":         round(self.hit_rate, 4),
            "miss_rate":        round(self.miss_rate, 4),
            "throughput_qps":   round(self.throughput, 4),
            "latency_p50_ms":   round(self.latency_percentile(50), 4),
            "latency_p95_ms":   round(self.latency_percentile(95), 4),
            "eviction_rate_pm": round(eviction_rate, 4),
            "cache_efficiency": round(self.cache_efficiency(), 4),
            "by_query_type":    self.hits_by_query_type(),
        }

    def print_report(self, redis_evictions: int = 0, elapsed_minutes: float = 1.0):
        r = self.report(redis_evictions, elapsed_minutes)
        print("\n" + "=" * 50)
        print("         MÉTRICAS DEL SISTEMA DE CACHÉ")
        print("=" * 50)
        print(f"  Total consultas   : {r['total_queries']}")
        print(f"  Hits              : {r['hits']}")
        print(f"  Misses            : {r['misses']}")
        print(f"  Hit rate          : {r['hit_rate']*100:.1f}%")
        print(f"  Miss rate         : {r['miss_rate']*100:.1f}%")
        print(f"  Throughput        : {r['throughput_qps']:.2f} req/s")
        print(f"  Latencia p50      : {r['latency_p50_ms']:.2f} ms")
        print(f"  Latencia p95      : {r['latency_p95_ms']:.2f} ms")
        print(f"  Eviction rate     : {r['eviction_rate_pm']:.2f} evictions/min")
        print(f"  Cache efficiency  : {r['cache_efficiency']:.4f}")
        print("\n  Por tipo de consulta:")
        for qtype, counts in sorted(r["by_query_type"].items()):
            total_q = counts["hits"] + counts["misses"]
            hr = counts["hits"] / total_q * 100 if total_q > 0 else 0
            print(f"    {qtype}: hits={counts['hits']}, misses={counts['misses']}, hit_rate={hr:.1f}%")
        print("=" * 50 + "\n")

    def save_to_file(self, path: str = "/app/metrics_output.json"):
        """Guarda el reporte en JSON para análisis posterior."""
        with open(path, "w") as f:
            json.dump(self.report(), f, indent=2)
        print(f"[Metrics] Reporte guardado en {path}")