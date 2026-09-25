"""วน benchmark: model × variant (× retrieval mode สำหรับ RAG)

ต่อโมเดล: unload -> เรียกครั้งแรกวัด cold load -> รันชุดทดสอบภายใต้ ResourceMonitor -> unload
"""
from ...retrieval.stubs import DenseStub, GraphStub, HybridStub
from .. import ollama_client, tasks
from ..config import TASKS
from ..resources import ResourceMonitor
from . import datasets, metrics

EXTRACT_TASKS = {"extract_profile": (datasets.extraction, tasks.extract_profile),
                 "extract_unmatch": (datasets.unmatch, tasks.extract_unmatch),
                 "extract_unmatch_sensitive": (datasets.unmatch_sensitive, tasks.extract_unmatch)}
CONFIG_KEY = {"extract_unmatch_sensitive": "extract_unmatch"}   # ใช้ config เดียวกัน ต่างแค่ชุดทดสอบ


def variant_name(v: dict) -> str:
    return ",".join(f"{k}={val}" for k, val in sorted(v.items())) or "default"


def unload_all():
    """ปล่อยทุกโมเดลออกจากหน่วยความจำ -> วัด RAM/GPU ของโมเดลที่ทดสอบได้ไม่ปนกัน"""
    for m in ollama_client.loaded():
        ollama_client.unload(m["name"])


def _cold_load(model, cfg, warm_fn):
    unload_all()
    res = warm_fn(cfg)
    return res["llm"]["load_ms"]


def _block_info(model, cold, mon):
    info = {"cold_load_ms": cold, **mon.summary()}
    own = [m for m in mon.gpu if m["name"].split(":")[0] == model.split(":")[0]]
    info["gpu_mem_gb"] = own[0]["vram_gb"] if own else info.get("gpu_mem_gb")
    info["other_models_loaded"] = len(mon.gpu) - len(own)
    return info


def run_extraction(task, models, variants, limit, log=print):
    data_fn, task_fn = EXTRACT_TASKS[task]
    samples = data_fn(limit)
    rows, blocks = [], {}
    for model in models:
        for v in variants:
            cfg = TASKS[CONFIG_KEY.get(task, task)].with_(model=model, **v)
            name = variant_name(v)
            cold = _cold_load(model, cfg, lambda c: task_fn(samples[0]["input"], c))
            with ResourceMonitor() as mon:
                for s in samples:
                    out = task_fn(s["input"], cfg)
                    rows.append({"task": task, "model": model, "variant": name, "id": s["id"], "llm": out["llm"], "raw": out["raw"],
                                 "validation": out["validation"], "score": metrics.extraction_score(out["extracted"], s["gold"]),
                                 "false_rf": metrics.false_red_flags(out["extracted"], s["gold"]),
                                 "extracted": out["extracted"]})
            blocks[(model, name)] = _block_info(model, cold, mon)
            log(f"  {model} [{name}] done {len(samples)} samples {blocks[(model, name)]}", flush=True)
        ollama_client.unload(model)
    return rows, blocks


def run_rag(models, modes, variants, limit, k=8, log=print):
    questions = datasets.rag(limit)
    dense, graph = DenseStub(), GraphStub()
    retrievers = {"dense": dense, "graph": graph, "hybrid": HybridStub(dense, graph)}
    contexts = {(q["qid"], m): retrievers[m].retrieve(q["question"], k) for q in questions for m in modes}
    rows, blocks = [], {}
    for model in models:
        for v in variants:
            cfg = TASKS["rag_answer"].with_(model=model, **v)
            name = variant_name(v)
            q0 = questions[0]
            cold = _cold_load(model, cfg, lambda c: tasks.rag_answer(q0["question"], contexts[(q0["qid"], modes[0])], c))
            with ResourceMonitor() as mon:
                for q in questions:
                    for mode in modes:
                        out = tasks.rag_answer(q["question"], contexts[(q["qid"], mode)], cfg)
                        rows.append({"task": "rag_answer", "model": model, "variant": name, "mode": mode, "qid": q["qid"],
                                     "needs": q["needs"], "answerable": q["answerable"], "answer": out["answer"],
                                     "llm": out["llm"], "context": out["context"], "citations": out["citations"],
                                     "score": metrics.rag_score(out["answer"], out["citations"], q)})
            blocks[(model, name)] = _block_info(model, cold, mon)
            log(f"  {model} [{name}] done {len(questions)}q × {len(modes)} modes {blocks[(model, name)]}", flush=True)
        ollama_client.unload(model)
    return rows, blocks
