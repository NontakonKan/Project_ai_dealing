"""กราฟเปรียบเทียบโมเดล (PNG สำหรับสไลด์) + ตาราง Markdown (อ่านตัวเลขได้ตรงๆ)

สี: palette อ้างอิงของ dataviz ตามลำดับที่ผ่านการตรวจตาบอดสีแบบคู่ติดกัน (ฟ้า ส้ม เขียวน้ำทะเล เหลือง) ไม่เกิน 4 ชุดต่อกราฟ
หน่วยต่างกัน (สัดส่วน / วินาที / เครดิต) -> แยกกราฟ ไม่ใช้แกน y สองแกน
"""
import json

from .data import OUT

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
FONT = "/System/Library/Fonts/Supplemental/Tahoma.ttf"      # มีอักษรไทย (ชื่อโมเดลมีคำว่า ใช้จริง / ฟรี)


def _setup():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager, pyplot as plt
    try:
        font_manager.fontManager.addfont(FONT)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=FONT).get_name()
    except Exception:
        pass
    plt.rcParams.update({"axes.edgecolor": GRID, "axes.labelcolor": INK_2, "xtick.color": INK_2,
                         "ytick.color": INK_2, "text.color": INK, "figure.facecolor": SURFACE,
                         "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})
    return plt


def _load(group):
    f = OUT / f"results_{group}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def _grouped(plt, rows, metrics, title, fname, subtitle=""):
    """สัดส่วน 0–1 หลายตัวชี้วัดต่อโมเดล: แท่งแนวตั้งจัดกลุ่ม ป้ายค่าที่ปลายแท่ง"""
    rows = [r for r in rows if all(r.get(k) is not None for k, _ in metrics)]
    if not rows:
        return None
    import numpy as np
    n, m = len(rows), len(metrics)
    w = 0.8 / m
    fig, ax = plt.subplots(figsize=(10, 4.6))
    x = np.arange(n)
    for i, (key, label) in enumerate(metrics):
        vals = [r[key] for r in rows]
        bars = ax.bar(x + (i - (m - 1) / 2) * w, vals, w - 0.02, color=SERIES[i], label=label, zorder=3)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.2f}", ha="center", va="bottom", fontsize=7.5, color=INK_2)
    ax.set_xticks(x, [r["model"] for r in rows], fontsize=9)
    ax.set_ylim(0, 1.12)
    ax.yaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=m, frameon=False, fontsize=9)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=18)
    if subtitle:
        ax.text(0, 1.035, subtitle, transform=ax.transAxes, fontsize=9, color=INK_2)
    fig.tight_layout()
    path = OUT / fname
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def _hbar(plt, rows, key, title, fname, unit, color_of=None, legend=None):
    """ค่าเดียวต่อโมเดล (เวลา / เครดิต / ความเร็ว): แท่งแนวนอนเรียงจากมากไปน้อย"""
    rows = sorted([r for r in rows if r.get(key) is not None], key=lambda r: r[key])
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(rows) + 1.4))
    colors = [color_of(r) if color_of else SERIES[0] for r in rows]
    bars = ax.barh([r["model"] for r in rows], [r[key] for r in rows], color=colors, height=0.6, zorder=3)
    top = max(r[key] for r in rows) or 1
    for b, r in zip(bars, rows):
        ax.text(b.get_width() + top * 0.01, b.get_y() + b.get_height() / 2, f"{r[key]:,} {unit}", va="center", fontsize=8.5, color=INK_2)
    ax.set_xlim(0, top * 1.18)
    ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if legend:
        from matplotlib.patches import Patch
        ax.legend(handles=[Patch(color=c, label=l) for l, c in legend], frameon=False, fontsize=9, loc="lower right")
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    path = OUT / fname
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def _table(sections):
    lines = ["# Model comparison — PSU Dealing", ""]
    for title, rows, cols in sections:
        if not rows:
            continue
        lines += [f"## {title}", "", "| model | " + " | ".join(c for c, _ in cols) + " |", "|---|" + "---|" * len(cols)]
        lines += ["| " + r["model"] + " | " + " | ".join(str(r.get(k, "-")) for _, k in cols) + " |" for r in rows]
        lines.append("")
    path = OUT / "summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def plot_all() -> list:
    plt = _setup()
    sbert, bert, local, api = (_load(g) for g in ("sbert", "bert", "local", "api"))
    llm = local + api
    out = [
        _grouped(plt, sbert, [("Hit@5", "Hit@5 (ค้นเจอใน 5 อันดับ)"), ("MRR@5", "MRR@5"), ("intent_acc", "แยกเจตนาถูก")],
                 "SBERT: ค้นความรู้ + แยกเจตนา", "sbert_quality.png", "คลัง 1,035 chunk · คำถาม 41 ข้อ · เจตนา 75 ประโยค"),
        _hbar(plt, sbert, "chunks_per_s", "SBERT: ความเร็วเข้ารหัส (สูง = เร็ว)", "sbert_speed.png", "chunk/s"),
        _grouped(plt, bert, [("Hit@1", "Hit@1 (อันดับ 1 ถูก)"), ("MRR@5", "MRR@5"), ("AUROC", "AUROC แยกคำถามนอกคลัง")],
                 "BERT cross-encoder: เรียงผลค้น + กันคำถามนอกคลัง", "bert_quality.png", "ผู้สมัคร 30 อันดับแรกจาก bge-m3 ชุดเดียวกันทุกโมเดล"),
        _hbar(plt, bert, "ms_per_pair", "BERT cross-encoder: เวลาต่อคู่ (ต่ำ = เร็ว)", "bert_speed.png", "ms"),
    ]
    metrics = [("answered", "ตอบคำถามที่มีข้อมูล"), ("refused", "ปฏิเสธคำถามนอกคลัง"),
               ("grounded", "มีหลักฐานในเอกสาร"), ("keyword", "มีคำตอบที่คาดหวัง")]
    out.append(_grouped(plt, local, metrics, "Local LLM (Ollama): คุณภาพการตอบ", "llm_local_quality.png",
                        "context ชุดเดียวกันทุกโมเดล · 52 คำถาม"))
    out.append(_grouped(plt, api, metrics, "API LLM (PSU AI): คุณภาพการตอบ", "llm_api_quality.png",
                        "context ชุดเดียวกันทุกโมเดล"))
    out.append(_hbar(plt, llm, "sec_p50", "LLM: เวลาตอบ (มัธยฐาน, ต่ำ = เร็ว)", "llm_latency.png", "s",
                     color_of=lambda r: SERIES[0] if r["provider"] == "local" else SERIES[1],
                     legend=[("Local", SERIES[0]), ("API", SERIES[1])]))
    out.append(_hbar(plt, [r for r in api if r.get("n")], "credits", "API LLM: เครดิตที่ใช้ทั้งชุด", "llm_api_credits.png", "เครดิต",
                     color_of=lambda r: SERIES[1]))
    out.append(_table([
        ("SBERT", sbert, [("Hit@5", "Hit@5"), ("MRR@5", "MRR@5"), ("intent", "intent_acc"), ("chunk/s", "chunks_per_s")]),
        ("BERT cross-encoder", bert, [("Hit@1", "Hit@1"), ("MRR@5", "MRR@5"), ("AUROC", "AUROC"), ("ms/pair", "ms_per_pair")]),
        ("LLM", llm, [("provider", "provider"), ("answered", "answered"), ("refused", "refused"), ("grounded", "grounded"),
                      ("keyword", "keyword"), ("cited", "cited"), ("s p50", "sec_p50"), ("credits", "credits"), ("errors", "errors")]),
    ]))
    return [p for p in out if p]
