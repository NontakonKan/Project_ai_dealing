"""วัด resource ระหว่างเรียก LLM: RAM (RSS) และ CPU ของ process Ollama + หน่วยความจำ GPU จาก /api/ps

ใช้: with ResourceMonitor() as mon: ... ; mon.summary()
"""
import subprocess
import threading

from . import ollama_client


def _ollama_procs():
    out = subprocess.run(["ps", "-axo", "rss=,%cpu=,command="], capture_output=True, text=True).stdout
    rss = cpu = 0.0
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and "ollama" in parts[2]:
            rss += float(parts[0])
            cpu += float(parts[1])
    return rss / 1024, cpu  # MB, % (100 = 1 core)


class ResourceMonitor:
    def __init__(self, interval=0.2):
        self.interval, self.samples = interval, []
        self._stop = threading.Event()

    def _loop(self):
        while not self._stop.is_set():
            self.samples.append(_ollama_procs())
            self._stop.wait(self.interval)

    def __enter__(self):
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join()
        try:
            self.gpu = ollama_client.loaded()
        except Exception:
            self.gpu = []

    def summary(self) -> dict:
        if not self.samples:
            return {}
        rss = [s[0] for s in self.samples]
        cpu = [s[1] for s in self.samples]
        return {"peak_rss_mb": round(max(rss)), "avg_cpu_pct": round(sum(cpu) / len(cpu)),
                "gpu_mem_gb": round(sum(m["vram_gb"] for m in self.gpu), 2), "samples": len(self.samples)}
