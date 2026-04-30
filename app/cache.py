import json
import os
import time
import redis
from metrics import MetricsStore

r = redis.Redis(host="redis", port=6379, decode_responses=True)

# Simula el tamaño real de una respuesta geoespacial serializada.
# La respuesta que recibe el sistema NO cambia: solo se agranda lo que Redis almacena.
CACHE_PAYLOAD_BYTES = int(os.getenv("CACHE_PAYLOAD_BYTES", "75000"))


def _make_cache_envelope(value):
    return {
        "result": value,
        "_payload": "x" * CACHE_PAYLOAD_BYTES,
    }


def _unwrap_cache_envelope(obj):
    if isinstance(obj, dict) and "result" in obj:
        return obj["result"]

    return obj


def get_from_cache(key: str):
    raw = r.get(key)

    if raw is not None:
        envelope = json.loads(raw)
        return _unwrap_cache_envelope(envelope), True

    return None, False


def set_in_cache(key: str, value, ttl: int = 60):
    envelope = _make_cache_envelope(value)
    r.set(key, json.dumps(envelope), ex=ttl)


def handle_query(key: str, compute_fn, metrics: MetricsStore, ttl: int = 60):
    start = time.perf_counter()

    cached, hit = get_from_cache(key)

    if hit:
        latency_ms = (time.perf_counter() - start) * 1000
        metrics.record_hit(key, latency_ms)
        return cached, True, latency_ms

    result = compute_fn()
    latency_ms = (time.perf_counter() - start) * 1000

    set_in_cache(key, result, ttl=ttl)
    metrics.record_miss(key, latency_ms)

    return result, False, latency_ms


def flush_cache():
    r.flushdb()


def cache_info() -> dict:
    stats = r.info("stats")
    memory = r.info("memory")

    return {
        "keyspace_hits": stats.get("keyspace_hits", 0),
        "keyspace_misses": stats.get("keyspace_misses", 0),
        "evicted_keys": stats.get("evicted_keys", 0),
        "total_commands": stats.get("total_commands_processed", 0),
        "used_memory": memory.get("used_memory", 0),
        "used_memory_human": memory.get("used_memory_human", "0B"),
        "maxmemory": memory.get("maxmemory", 0),
        "maxmemory_human": memory.get("maxmemory_human", "0B"),
    }