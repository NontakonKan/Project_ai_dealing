"""ตรวจ hardware + แนะนำโมเดลที่รันได้ (ใช้เป็นหลักฐาน "เลือกโมเดลเหมาะกับ hardware")"""
import os
import platform
import subprocess

from . import ollama_client

MEMORY_FRACTION = 0.6   # ใช้ได้ไม่เกิน 60% ของ unified memory (เหลือให้ OS, Vector DB, Neo4j)
KV_OVERHEAD = 1.25      # เผื่อ KV cache + runtime


def _sysctl(key):
    try:
        return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def detect() -> dict:
    ram = int(_sysctl("hw.memsize") or 0)
    return {"os": platform.platform(), "chip": _sysctl("machdep.cpu.brand_string") or platform.processor(),
            "cpu_cores": os.cpu_count(), "ram_gb": round(ram / 2**30, 1),
            "gpu": "Apple Silicon (Metal, unified memory)" if platform.machine() == "arm64" else "unknown"}


def recommend(hw=None) -> list:
    hw = hw or detect()
    budget_gb = hw["ram_gb"] * MEMORY_FRACTION
    rows = []
    for m in ollama_client.list_models():
        need = m["size_gb"] * KV_OVERHEAD
        rows.append({**m, "est_mem_gb": round(need, 1), "fits": need <= budget_gb})
    return sorted(rows, key=lambda r: r["size_gb"])
