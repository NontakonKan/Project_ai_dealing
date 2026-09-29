"""แยกเจตนาข้อความด้วยความหมาย — ไม่ดักคำตายตัว

ปัญหาเดิม (log LINE): "ลบโปรไฟล์", "ส่งลบโปรไฟล์" ไม่ตรงคำในรายการ ("ลบข้อมูลของฉัน", "ลบบัญชี")
-> ตกไปเป็นคำถามปรึกษา แล้วตอบว่า "ไม่มีข้อมูลในคลัง"

วิธี (3 ชั้น):
1. SBERT: bge-m3 (ตัวเดียวกับ Dense RAG) เทียบ cosine กับประโยคตัวอย่างของแต่ละเจตนา -> คะแนนความหมาย
2. BM25 บน character trigram (ภาษาไทยไม่มีช่องว่างระหว่างคำ) -> คะแนนคำที่ใช้ร่วมกัน
3. รวมคะแนน -> ชัดเจน (คะแนนสูง + ห่างอันดับ 2) ใช้เลย / ก้ำกึ่ง ให้ LLM Local เลือกจากตัวเลือก 3 อันดับแรก
   (ข้อความไม่ออกนอกเครื่อง; LLM เลือกนอกตัวเลือกไม่ได้)

ประโยคตัวอย่างแยกจากชุดทดสอบ (app/intent_eval.py) — ห้ามคัดลอกประโยคทดสอบมาใส่ที่นี่
"""
import math
import re
from collections import Counter
from functools import lru_cache

# เจตนา -> (คำอธิบายให้ LLM, ประโยคตัวอย่าง)
INTENTS = {
    "find_match": ("คำสั่ง: ให้ระบบแนะนำหรือจับคู่คนให้ตอนนี้ (ไม่ใช่คำถามว่าควรทำตัวอย่างไร)", [
        "หาคู่ให้หน่อย", "แนะนำคนให้หน่อย", "มีใครเหมาะกับผมบ้าง", "อยากมีแฟน ช่วยหาให้หน่อย",
        "ขอดูคนที่เข้ากับฉัน", "จับคู่ให้หน่อย", "มีคนน่าคุยไหม", "หาคนคุยให้หน่อย", "ขอคนใหม่อีกคน",
        "แนะนำคนต่อไปเลย"]),
    "show_profile": ("คำสั่ง: ขอดูข้อมูล/โปรไฟล์ของตัวเองที่ระบบเก็บไว้ (ดูเฉยๆ ไม่ลบ)", [
        "โปรไฟล์ของฉัน", "ดูข้อมูลของฉัน", "ระบบจำอะไรเกี่ยวกับฉันบ้าง", "ขอดูโปรไฟล์หน่อย",
        "ตอนนี้มีข้อมูลอะไรของผมบ้าง", "ข้อมูลที่เก็บไว้มีอะไรบ้าง", "เช็คโปรไฟล์ให้หน่อย",
        "บอกหน่อยว่ารู้อะไรเกี่ยวกับฉัน"]),
    "delete_me": ("คำสั่ง: ลบข้อมูล บัญชี หรือโปรไฟล์ของตัวเองออกจากระบบ", [
        "ลบข้อมูลของฉัน", "ลบบัญชีของฉัน", "ไม่อยากใช้แล้ว ลบข้อมูลทั้งหมดให้หน่อย", "ช่วยลบประวัติของฉันทิ้ง",
        "ขอยกเลิกบัญชี", "เอาข้อมูลของผมออกจากระบบ", "ล้างข้อมูลทั้งหมดของฉัน", "ลบทุกอย่างที่เก็บเกี่ยวกับฉัน"]),
    "unmatch": ("คำสั่ง: ยกเลิก/ไม่คุยต่อกับคู่ที่ระบบแนะนำให้ (ไม่ใช่เรื่องเลิกกับแฟนจริง)", [
        "เลิกคุยกับคนนี้", "ไม่อยากคุยกับเขาต่อแล้ว", "คนนี้ไม่ใช่ ไม่ไปต่อ", "ยกเลิกคู่นี้",
        "ไม่ถูกใจคนที่แนะนำมา", "ขอเลิกแมตช์", "คุยแล้วไม่เวิร์ค ขอหยุด"]),
    "recall_memory": ("ถามว่าบอทจำสิ่งที่ผู้ใช้เคยเล่าให้บอทฟังได้ไหม (ความจำของบอท ไม่ใช่การคิดถึงคน)", [
        "จำได้ไหมที่ผมเคยบอก", "ครั้งก่อนผมเล่าว่าอะไร", "เมื่อวานผมบอกว่าชอบอะไรนะ",
        "ที่เคยคุยกันเรื่องแฟนเก่าจำได้ไหม", "ผมเคยบอกคณะอะไรไป"]),
    "ask_advice": ("คำถาม/ขอคำปรึกษาเรื่องความรัก ความสัมพันธ์ การจีบ การเดต การเลิกรา อกหัก red flag yellow flag green flag สุขภาพทางเพศ", [
        "ควรเริ่มทักยังไงดี", "แฟนหึงมากทำไงดี", "gaslighting คืออะไร", "คนคุยหายไปเฉยๆ ควรทำไง",
        "จะรู้ได้ไงว่าเค้าชอบเรา", "ทฤษฎีความรักมีอะไรบ้าง", "ควรตรวจโรคติดต่อทางเพศบ่อยแค่ไหน",
        "นัดเจอคนจากแอปครั้งแรกควรระวังอะไร", "อยากปรึกษาเรื่องความรักหน่อย", "ไม่กล้าปฏิเสธ ควรพูดยังไง",
        "แฟนไม่ตอบแชทควรทำยังไง", "ทำไมความรักถึงจืดจาง", "วิธีตั้งขอบเขตกับคนคุย", "คนคุยไม่ชัดเจนต้องทำยังไง",
        "จะรู้ได้ไงว่าแฟนนอกใจ", "วิธีจีบคนที่แอบชอบ", "ทำไมถึงลืมแฟนเก่าไม่ได้", "stonewalling คืออะไร",
        "red flag คืออะไร", "yellow flag คืออะไร", "green flag คืออะไร", "เรดแฟลกคืออะไร",
        "นัดครั้งแรกนัดยังไง", "เดทแรกควรทำยังไง", "สัญญาณอันตรายในความสัมพันธ์"]),
    "followup": ("ถามต่อจากคำตอบก่อนหน้า เช่น ขอตัวอย่าง ขอรายละเอียดข้อใดข้อหนึ่ง หรือถามกรณีต่อไป", [
        "ยกตัวอย่างหน่อย", "ขยายความข้อสองหน่อย", "แล้วถ้าเขาไม่ตอบล่ะ", "อธิบายเพิ่มอีกนิด",
        "ข้อแรกหมายถึงอะไร", "ทำตามแล้วไม่ได้ผล ทำไงต่อ"]),
    "chat": ("บอกเล่าบุคลิก ความชอบ สเปกคนที่ชอบ ไลฟ์สไตล์ หรือข้อมูลตัวเองเพื่อการหาคู่ รวมถึงการทักทาย", [
        "หวัดดี", "สวัสดีครับ", "สวัสดีค่ะ", "ดีครับ", "ดีค่ะ", "ทักทายครับ", "hello", "hi",
        "ผมชอบเล่นเกม", "อยากได้คนใจเย็น", "เปลี่ยนใจชอบผิวดำ", "ผมเรียนวิศวะ",
        "วันนี้เหนื่อยจัง", "ขอบคุณครับ", "ชอบคนตลกๆ", "ผมเป็นคนเก็บตัว", "ไม่ชอบคนสูบบุหรี่",
        "ชอบคนอ่านหนังสือ เวลาว่างชอบดูหนัง", "วันนี้ทำกับข้าวกินเอง", "ชอบทำอาหาร", "ชอบฟังเพลง", "555", "โอเคครับ"]),
    "out_of_domain": ("คำถามทั่วไป นอกเรื่อง ปริศนา กวน เล่นมุก วิทยาศาสตร์ คณิตศาสตร์ การเมือง อาหาร อากาศ หรือเรื่องสัตว์ ที่ไม่เกี่ยวกับการหาคู่หรือข้อมูลตัวเอง", [
        "หมากับแมวอะไรน่ารักกว่า", "แมวกับไก่ ตัวอะไรอร่อยกว่า", "1+1 ได้เท่าไหร่", "ใครชนะเลือกตั้ง",
        "ผีมีจริงไหม", "ช่วยเขียนโค้ดหน่อย", "โลกกลมหรือแบน", "สุนัขพันธุ์ไหนดี", "เล่นมุกให้ฟังหน่อย",
        "ส้มตำกับต้มยำอะไรอร่อยกว่า", "แนะนำร้านอาหารหน่อย", "ดูดวงให้หน่อย", "กินข้าวกับอะไรดี", "กินอะไรดี",
        "วันนี้อากาศเป็นยังไง", "ไปเที่ยวไหนดี", "ขอเลขเด็ดงวดนี้หน่อย"]),
}
ROUTE = {"followup": "ask_advice"}   # คำถามต่อเนื่องไปทางเดียวกับคำถามปรึกษา (advice.handle จัดการประวัติต่อ)

# BM25 เป็นแค่ตัวช่วยตัดสินเมื่อความหมายใกล้กัน: วัดจริง น้ำหนัก 0.25 ทำให้ "ลบโปรไฟล์" -> show_profile
# (trigram "โปรไฟล์" ตรงกับตัวอย่างดูโปรไฟล์ ขณะที่ความต่างอยู่ที่คำกริยา "ลบ" ซึ่ง SBERT จับได้)
W_DENSE, W_BM25 = 0.9, 0.1
MIN_SIM = 0.55       # ความหมายใกล้ตัวอย่างอย่างน้อยเท่านี้จึงเชื่อได้โดยไม่ต้องถาม LLM
MIN_MARGIN = 0.04    # ห่างจากเจตนาอันดับ 2 อย่างน้อยเท่านี้
TOP_N = 3            # ตัวเลือกที่ส่งให้ LLM


def _trigrams(text):
    t = re.sub(r"\s+", "", text.lower())
    return [t[i:i + 3] for i in range(max(1, len(t) - 2))]


class _BM25:
    def __init__(self, docs, k1=1.2, b=0.75):
        self.docs = [Counter(_trigrams(d)) for d in docs]
        self.len = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.len) / len(self.len)
        df = Counter(g for d in self.docs for g in d)
        n = len(self.docs)
        self.idf = {g: math.log(1 + (n - c + 0.5) / (c + 0.5)) for g, c in df.items()}
        self.k1, self.b = k1, b

    def self_score(self, query):
        q = _trigrams(query)
        return sum(self.idf.get(g, 0.0) * (self.k1 + 1) / (1 + self.k1 * (1 - self.b + self.b * len(q) / self.avg))
                   for g in set(q))

    def scores(self, query):
        q = _trigrams(query)
        out = []
        for d, dl in zip(self.docs, self.len):
            s = 0.0
            for g in q:
                if g in d:
                    tf = d[g]
                    s += self.idf[g] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avg))
            out.append(s)
        return out


@lru_cache(maxsize=1)
def _index():
    import numpy as np
    from pipelines.dense.embedding import encode
    labels = [name for name, (_, ex) in INTENTS.items() for _ in ex]
    texts = [e for _, (_, ex) in INTENTS.items() for e in ex]
    return labels, texts, encode(texts, role="document"), _BM25(texts), np


def scores(text, use_dense=True, use_bm25=True) -> dict:
    """{เจตนา: คะแนนรวม} + รายละเอียด (ใช้ใน log และ intent_eval)"""
    labels, texts, vecs, bm25, np = _index()
    dense = {}
    if use_dense:
        from pipelines.dense.embedding import encode
        sims = vecs @ encode([text], role="query")[0]
        for lab, s in zip(labels, sims):
            dense.setdefault(lab, []).append(float(s))
        dense = {k: float(np.mean(sorted(v, reverse=True)[:2])) for k, v in dense.items()}   # เฉลี่ย 2 ตัวอย่างที่ใกล้สุด
    lex = {}
    if use_bm25:
        raw = bm25.scores(text)
        for lab, s in zip(labels, raw):
            lex[lab] = max(lex.get(lab, 0.0), s)
        # หารด้วยคะแนนสูงสุดที่ข้อความนี้ทำได้ (ถ้าตัวอย่างเหมือนข้อความทุกตัวอักษร) -> 0..1 = สัดส่วนที่ตรงจริง
        # (เดิมหารด้วยค่าสูงสุดระหว่างเจตนา: ตรงนิดเดียวก็ได้ 1.0 เช่น "ผมอายุ 21" -> delete_me 1.0)
        full = bm25.self_score(text) or 1.0
        lex = {k: min(1.0, v / full) for k, v in lex.items()}
    w_d, w_b = (W_DENSE, W_BM25) if use_dense and use_bm25 else ((1, 0) if use_dense else (0, 1))
    fused = {k: w_d * dense.get(k, 0) + w_b * lex.get(k, 0) for k in INTENTS}
    return {"fused": fused, "dense": dense, "bm25": lex}


def _ask_llm(text, candidates):
    from pipelines.llm import providers
    from pipelines.llm.config import TASKS
    cfg = TASKS["classify_intent"]
    options = "\n".join(f"- {c}: {INTENTS[c][0]}" for c in candidates)
    msgs = [{"role": "system", "content": "จำแนกเจตนาของข้อความผู้ใช้ในแชทบอทหาคู่ ตอบชื่อเจตนาเพียงชื่อเดียวจากตัวเลือกนี้เท่านั้น:\n"
                                          + options},
            {"role": "user", "content": text}]
    out = providers.chat(cfg.model, msgs, cfg.gen, fallback=cfg.fallback or None).text.strip().lower()
    return next((c for c in candidates if c in out), None)


GREETING_WORDS = {"หวัดดี", "สวัสดี", "ดีครับ", "ดีค่ะ", "ดีจ้า", "ดีคับ", "หวัดดีครับ", "หวัดดีค่ะ", "hello", "hi", "hey"}


def is_pure_greeting(text: str) -> bool:
    clean = re.sub(r"[^\w\s]", "", text.strip().lower())
    words = clean.split()
    return bool(words and all(w in GREETING_WORDS for w in words))


def classify(text, use_llm=True, use_dense=True, use_bm25=True) -> tuple:
    """-> (เจตนา, ข้อมูลประกอบการตัดสิน) — เจตนา followup ถูก map เป็น ask_advice ใน ROUTE

    ความหมายชัด (SBERT สูงพอ + ห่างอันดับ 2) -> ใช้คำตอบของ SBERT
    ก้ำกึ่ง -> LLM เลือกจากตัวเลือกอันดับต้นของคะแนนรวม (BM25 ช่วยเสนอตัวเลือกที่คำตรงกัน)
    วัดจริง: ให้คะแนนรวมตัดสินตรงๆ ทำให้ "ลบโปรไฟล์" (SBERT delete_me 0.82 vs show_profile 0.75)
    กลายเป็น show_profile เพราะ trigram "โปรไฟล์" -> BM25 ใช้เสนอตัวเลือก ไม่ใช้ตัดสิน"""
    if is_pure_greeting(text):
        return "chat", {"top": [("chat", 1.0)], "by": "greeting"}
    s = scores(text, use_dense, use_bm25)
    ranked = sorted(s["fused"].items(), key=lambda kv: -kv[1])
    by_meaning = sorted((s["dense"] if use_dense else s["fused"]).items(), key=lambda kv: -kv[1])
    (best, sim), (_, second) = by_meaning[0], by_meaning[1]
    info = {"top": [(k, round(v, 3)) for k, v in by_meaning[:TOP_N]], "by": "similarity"}
    if use_llm and (sim < MIN_SIM or sim - second < MIN_MARGIN):
        candidates = list(dict.fromkeys([k for k, _ in by_meaning[:TOP_N]] + [ranked[0][0]]))
        try:
            picked = _ask_llm(text, candidates)
        except Exception:
            picked = None
        if picked:
            best, info["by"] = picked, "llm"
    return best, info

