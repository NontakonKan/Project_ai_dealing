"""Prompt templates แยกตามงาน + variant (ใช้เทียบใน benchmark)"""
from ..common import taxonomy
from .schemas import PROFILE_FIELDS, UNMATCH_FIELDS, allowed_ids


def _id_list(fields, with_definitions=False):
    labels = taxonomy.labels()
    definitions = {t["id"]: t["definition"] for g in taxonomy.GROUPS for t in taxonomy.load().get(g, []) if t.get("definition")}
    seen, lines = set(), []
    for ids in allowed_ids(fields).values():
        for i in ids:
            if i not in seen:
                seen.add(i)
                d = definitions.get(i)
                lines.append(f"- {i} = {labels[i]}" + (f" (หมายถึง: {d})" if d and with_definitions else ""))
    return "\n".join(lines)


EXTRACT_SYSTEM = """คุณคือระบบสกัดข้อมูลบุคลิกภาพจากแชทภาษาไทย
ตอบเป็น JSON เท่านั้น ใช้ได้เฉพาะรหัสในรายการ ห้ามเดา
ทุกรายการต้องมี "evidence" = ข้อความที่คัดลอกมาจากแชทตรงตัว ถ้าไม่มีหลักฐานในแชทห้ามใส่
field:
- hobbies = สิ่งที่ผู้พูดชอบทำ เช่น "ชอบฟังเพลง", "ทำกับข้าว"
- traits = นิสัยของผู้พูดเอง เช่น "เป็นคนใจเย็น", "ไม่ชอบที่คนเยอะ" (= trait:introvert)
- comm_style = สไตล์การแชท/สื่อสารของผู้พูด
- self_described = รูปร่าง/สีผิวที่ผู้พูดบอกเกี่ยวกับ "ตัวเอง" เช่น "เราหุ่นหมีนะ" (ห้ามเดา)
- wants = นิสัยหรือรูปลักษณ์ที่ผู้พูดอยากได้ในคู่ ใช้เมื่อมีคำว่า "ชอบคน...", "อยากได้คน...", "สเปก..."
- avoids = พฤติกรรมหรือรูปลักษณ์ของคู่ที่ผู้พูดไม่ชอบ เช่น "ไม่เอาคน...", "ไม่ชอบคน..."

รหัสที่ใช้ได้:
{ids}"""

EXTRACT_FEWSHOT = [
    {"role": "user", "content": "แชท: เลิกงานแล้ว ชอบเข้ายิมกับถ่ายรูป เป็นคนตรงต่อเวลา ชอบคนตลกๆ ไม่ชอบคนขี้หึง"},
    {"role": "assistant", "content": '{"hobbies":[{"id":"hobby:gym","evidence":"เข้ายิม"},{"id":"hobby:photography","evidence":"ถ่ายรูป"}],'
     '"traits":[{"id":"trait:responsible","evidence":"ตรงต่อเวลา"}],"comm_style":[],'
     '"self_described":[],"wants":[{"id":"trait:funny","evidence":"ตลกๆ"}],"avoids":[{"id":"rf:possessive","evidence":"ขี้หึง"}]}'},
    {"role": "user", "content": "แชท: วันหยุดอยู่บ้านอ่านนิยาย ตอบแชทช้านะ เราหุ่นหมีๆ ชอบคนใจดี ผิวขาว"},
    {"role": "assistant", "content": '{"hobbies":[{"id":"hobby:reading","evidence":"อ่านนิยาย"}],'
     '"traits":[{"id":"trait:homebody","evidence":"วันหยุดอยู่บ้าน"}],"comm_style":[{"id":"comm:slow_texter","evidence":"ตอบแชทช้า"}],'
     '"self_described":[{"id":"body:curvy","evidence":"หุ่นหมี"}],'
     '"wants":[{"id":"trait:kind","evidence":"ใจดี"},{"id":"skin:fair","evidence":"ผิวขาว"}],"avoids":[]}'},
]

UNMATCH_SYSTEM = """ผู้ใช้กำลังบอกเหตุผลที่เลิกคุยกับคู่ที่ระบบแนะนำ แยกเหตุผลเป็น 3 ช่อง (JSON):
- red_flags = "พฤติกรรม" ของอีกฝ่าย เช่น หายเงียบ หึงหวง โกหก พูดจาไม่ดี
- appearance = "รูปร่าง/สีผิว" ของอีกฝ่าย เช่น อ้วน ผอม ดำ ขาว (ห้ามใส่ใน red_flags เด็ดขาด)
- hygiene = เรื่องกลิ่นตัว/ความสะอาด (ห้ามใส่ใน red_flags)
ทุกรายการ: {{"id":..., "evidence": คัดลอกจากข้อความตรงตัว, "severity": 0-1 (1 = รับไม่ได้เลย)}}
ช่องไหนไม่มีให้เป็น []

รหัสที่ใช้ได้:
{ids}"""

UNMATCH_FEWSHOT = [
    {"role": "user", "content": "เหตุผล: ไม่ไหว ขอดูมือถือตลอด แล้วก็โกหกบ่อย"},
    {"role": "assistant", "content": '{"red_flags":[{"id":"rf:possessive","evidence":"ขอดูมือถือ","severity":0.8},'
     '{"id":"rf:dishonest","evidence":"โกหก","severity":0.9}],"appearance":[],"hygiene":[]}'},
    {"role": "user", "content": "เหตุผล: ผอมไปหน่อย แล้วเวลาโกรธชอบเงียบใส่ ตัวเหม็นด้วย"},
    {"role": "assistant", "content": '{"red_flags":[{"id":"rf:stonewalling","evidence":"เงียบใส่","severity":0.8}],'
     '"appearance":[{"id":"body:slim","evidence":"ผอม","severity":0.5}],'
     '"hygiene":[{"id":"hygiene:self_care","evidence":"ตัวเหม็น","severity":0.7}]}'},
]

RAG_SYSTEM = {
    "default": """คุณคือผู้ช่วยให้คำปรึกษาเรื่องความสัมพันธ์ ตอบเป็นภาษาไทยที่เป็นกันเอง
กติกา:
1. ใช้ข้อมูลใน CONTEXT เท่านั้น ห้ามแต่งเพิ่ม
2. ทุกประโยคที่ใช้ข้อมูลจาก CONTEXT ต้องลงท้ายด้วยเลขอ้างอิง เช่น "ความรักมี 3 องค์ประกอบ [2]"
3. ถ้า CONTEXT ไม่มีข้อมูลที่ตอบคำถามได้ ให้ตอบว่า "ไม่มีข้อมูลเพียงพอ" เท่านั้น""",
    "concise": """ตอบคำถามเป็นภาษาไทยไม่เกิน 4 ประโยค โดยใช้เฉพาะ CONTEXT พร้อมอ้างอิง [หมายเลข]
ถ้าไม่มีข้อมูลใน CONTEXT ตอบว่า "ไม่มีข้อมูลเพียงพอ" """,
}

EXPLAIN_SYSTEM = """คุณคือผู้ช่วยจับคู่ใน LINE อธิบายให้ผู้ใช้ A ฟังว่าทำไมระบบแนะนำ B
ตอบภาษาไทยเป็นกันเอง สั้นกระชับ 3 ส่วน: (1) จุดที่เข้ากัน (2) จุดที่ควรระวัง (3) เคล็ดลับเริ่มคุย
กติกา:
1. ใช้ข้อมูลจากโปรไฟล์และ CONTEXT เท่านั้น ห้ามเดาหรือแต่งนิสัยที่ไม่มีในข้อมูล
2. ประโยคที่ใช้ข้อมูลจาก CONTEXT ต้องลงท้ายด้วยเลขอ้างอิง เช่น "ทั้งคู่ชอบเล่นเกม [2]"
3. "จุดที่ควรระวัง" ต้องมาจากความต่างที่มีอยู่จริงในข้อมูล ถ้าไม่มีให้บอกว่าไม่พบจุดที่น่ากังวล
4. ห้ามพูดถึงรูปร่าง หน้าตา สีผิว และห้ามบอกว่าใครเคยถูกรายงาน"""


def extract_messages(text, variant="few_shot"):
    msgs = [{"role": "system", "content": EXTRACT_SYSTEM.format(ids=_id_list(PROFILE_FIELDS))}]
    if variant == "few_shot":
        msgs += EXTRACT_FEWSHOT
    return msgs + [{"role": "user", "content": f"แชท: {text}"}]


# ตัวอย่างสำนวน "เล่าพฤติกรรม" (ไม่ใช้คำตรงจาก aliases) — เขียนใหม่ ไม่คัดลอกจากชุดทดสอบ
UNMATCH_PARAPHRASE = [
    {"role": "user", "content": "เหตุผล: ไปไหนต้องส่งโลเคชันให้ดูตลอด ไม่ส่งก็งอน เหนื่อยมาก"},
    {"role": "assistant", "content": '{"red_flags":[{"id":"rf:possessive","evidence":"ไปไหนต้องส่งโลเคชันให้ดูตลอด","severity":0.8}],'
     '"appearance":[],"hygiene":[]}'},
    {"role": "user", "content": "เหตุผล: นัดกี่ทีก็เลื่อน วันนี้หวานพรุ่งนี้ห่างเหิน งงไปหมด"},
    {"role": "assistant", "content": '{"red_flags":[{"id":"rf:inconsistent","evidence":"นัดกี่ทีก็เลื่อน วันนี้หวานพรุ่งนี้ห่างเหิน","severity":0.7}],'
     '"appearance":[],"hygiene":[]}'},
]


def unmatch_messages(reason, variant="few_shot"):
    """variant: zero_shot | few_shot (ค่าเริ่มต้น) | few_shot_defs (+คำนิยาม) | few_shot_para (+ตัวอย่างสำนวนเล่าพฤติกรรม)"""
    defs = variant == "few_shot_defs"
    msgs = [{"role": "system", "content": UNMATCH_SYSTEM.format(ids=_id_list(UNMATCH_FIELDS, with_definitions=defs))}]
    if variant.startswith("few_shot"):
        msgs += UNMATCH_FEWSHOT
    if variant == "few_shot_para":
        msgs += UNMATCH_PARAPHRASE
    return msgs + [{"role": "user", "content": f"เหตุผล: {reason}"}]


def rag_messages(query, context, variant="default"):
    return [{"role": "system", "content": RAG_SYSTEM.get(variant, RAG_SYSTEM["default"])},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nคำถาม: {query}\n"
                                        "(ตอบจาก CONTEXT และใส่เลขอ้างอิง [n] ท้ายประโยค)"}]


def explain_messages(profile_a, profile_b, context, variant="default"):
    return [{"role": "system", "content": EXPLAIN_SYSTEM},
            {"role": "user", "content": f"โปรไฟล์ A:\n{profile_a}\n\nโปรไฟล์ B:\n{profile_b}\n\nCONTEXT:\n{context}\n\n"
                                        "(เขียน 3 ส่วน ใส่เลขอ้างอิง [n] ท้ายประโยคที่มาจาก CONTEXT)"}]
