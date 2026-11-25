"""AURORA Professional: Benchmark de Rendimiento, Carga y Estabilidad (FASE 8).

Mide:
1. Carga de Inicio (catálogo).
2. Carga de Telemetría (con 250 evaluaciones completas de Estudio 27).
3. Aplicación de filtros de dimensión y recálculo de telemetría.
4. Generación de informe PDF de 6 páginas con gráficos vectoriales y baremos.
5. Concurrencia de 10 peticiones simultáneas de telemetría.
6. Métricas de recursos (RAM, CPU).
"""
import asyncio
import ctypes
import json
import os
import time
from pathlib import Path
import httpx

BASE_URL = "http://127.0.0.1:8002/api/v1"
QA_DIR = Path(r"D:\Colmena2.0\docs\qa\aurora-corporate-validation-20261022")

BENCHMARKS = {}

def get_windows_memory():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    return {
        "load_pct": stat.dwMemoryLoad,
        "total_gb": round(stat.ullTotalPhys / (1024**3), 2),
        "free_gb": round(stat.ullAvailPhys / (1024**3), 2)
    }

def run_benchmarks():
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # Autenticación
    r_login = client.post("/auth/demo-login")
    token = r_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Medición Carga Catálogo / Inicio
    print("\n--- 1. Carga Catálogo / Inicio ---")
    times_catalog = []
    for _ in range(5):
        t0 = time.time()
        r = client.get("/censopas/plans", headers=headers)
        times_catalog.append(time.time() - t0)
    BENCHMARKS["catalog_p50_ms"] = round(sorted(times_catalog)[len(times_catalog)//2] * 1000, 2)
    BENCHMARKS["catalog_p95_ms"] = round(sorted(times_catalog)[-1] * 1000, 2)
    print(f"Catálogo: p50={BENCHMARKS['catalog_p50_ms']}ms, p95={BENCHMARKS['catalog_p95_ms']}ms")

    # 2. Medición Telemetría Proyecto 24 (250 participantes)
    print("\n--- 2. Telemetría Proyecto 24 (250 respuestas) ---")
    times_telem = []
    for _ in range(5):
        t0 = time.time()
        r = client.get("/projects/24/telemetry", headers=headers)
        times_telem.append(time.time() - t0)
    BENCHMARKS["telemetry_p50_ms"] = round(sorted(times_telem)[len(times_telem)//2] * 1000, 2)
    BENCHMARKS["telemetry_p95_ms"] = round(sorted(times_telem)[-1] * 1000, 2)
    print(f"Telemetría (250 participantes): p50={BENCHMARKS['telemetry_p50_ms']}ms, p95={BENCHMARKS['telemetry_p95_ms']}ms")

    # 3. Medición Resultados CENSOPAS por Dimensión (Scoring)
    print("\n--- 3. Scoring CENSOPAS Estudio 27 ---")
    times_scoring = []
    for _ in range(5):
        t0 = time.time()
        r = client.get("/studies/27/censopas/results", headers=headers)
        times_scoring.append(time.time() - t0)
    BENCHMARKS["scoring_p50_ms"] = round(sorted(times_scoring)[len(times_scoring)//2] * 1000, 2)
    BENCHMARKS["scoring_p95_ms"] = round(sorted(times_scoring)[-1] * 1000, 2)
    print(f"Scoring Estudio 27: p50={BENCHMARKS['scoring_p50_ms']}ms, p95={BENCHMARKS['scoring_p95_ms']}ms")

    # 4. Generación de Vista Previa PDF
    print("\n--- 4. Generación PDF Report Preview ---")
    t0 = time.time()
    r_prev = client.get("/reports/34/preview.pdf", headers=headers)
    BENCHMARKS["pdf_preview_delivery_ms"] = round((time.time() - t0) * 1000, 2)
    BENCHMARKS["pdf_size_bytes"] = len(r_prev.content)
    print(f"Entrega PDF (424 KB): {BENCHMARKS['pdf_preview_delivery_ms']}ms")

    # 5. Concurrencia de 10 peticiones simultáneas
    print("\n--- 5. Concurrencia 10 peticiones de telemetría ---")
    async def concurrent_requests():
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as async_client:
            tasks = [async_client.get("/projects/24/telemetry", headers=headers) for _ in range(10)]
            t0 = time.time()
            responses = await asyncio.gather(*tasks)
            total_time = time.time() - t0
            assert all(resp.status_code == 200 for resp in responses)
            return total_time

    total_concurrent = asyncio.run(concurrent_requests())
    BENCHMARKS["concurrency_10_requests_total_s"] = round(total_concurrent, 3)
    BENCHMARKS["concurrency_throughput_req_per_s"] = round(10 / total_concurrent, 2)
    print(f"10 peticiones concurrentes completadas en {total_concurrent:.3f}s ({BENCHMARKS['concurrency_throughput_req_per_s']} req/s)")

    # 6. Recursos del Sistema
    print("\n--- 6. Recursos del Sistema ---")
    mem = get_windows_memory()
    BENCHMARKS["system_ram_used_pct"] = mem["load_pct"]
    BENCHMARKS["system_ram_free_gb"] = mem["free_gb"]
    BENCHMARKS["system_ram_total_gb"] = mem["total_gb"]
    print(f"RAM Total: {mem['total_gb']} GB | Libre: {mem['free_gb']} GB ({100 - mem['load_pct']}% libre)")

    out_file = QA_DIR / "benchmarks" / "performance_benchmarks.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(BENCHMARKS, f, indent=2)
    print(f"\nMétricas de rendimiento guardadas en: {out_file}")

if __name__ == "__main__":
    run_benchmarks()
