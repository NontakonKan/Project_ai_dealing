"""ค่านิยมที่อยู่ "ในข้อความเท่านั้น" (ไม่มีรหัสใน taxonomy -> Graph มองไม่เห็น, Dense ต้องจับความหมายเอง)

เหตุผล: แชทจริงมีข้อมูลนอก taxonomy เสมอ ถ้า mock มีแค่รหัส taxonomy, Dense จะไม่มีข้อมูลเฉพาะตัว
และการทดลอง Hybrid จะตอบไม่ได้ว่า Dense ช่วยเติมอะไร — แต่ละค่าเขียนได้หลายสำนวน (ต้องใช้ความหมาย ไม่ใช่ string match)
"""
VALUES = {
    "family": {
        "want_kids": ["อยากมีลูกในอนาคต", "ฝันอยากมีครอบครัวอบอุ่นมีลูกสักคนสองคน", "ชอบเด็ก อยากเป็นพ่อแม่คน"],
        "no_kids": ["ยังไม่อยากมีลูก", "ไม่ได้วางแผนจะมีลูก", "อยากใช้ชีวิตคู่แบบไม่มีลูก"],
    },
    "place": {
        "city": ["อยากใช้ชีวิตในเมืองใหญ่", "อยากทำงานที่กรุงเทพฯ", "ชอบความสะดวกของเมือง"],
        "hometown": ["อยากกลับไปอยู่บ้านเกิดต่างจังหวัด", "ฝันอยากมีบ้านสวนเงียบๆ", "ไม่อยากอยู่เมืองใหญ่ วุ่นวาย"],
    },
    "money": {
        "saver": ["ชอบเก็บออม วางแผนการเงิน", "ใช้เงินอย่างระมัดระวัง มีเงินเก็บทุกเดือน", "จดรายรับรายจ่ายตลอด"],
        "spender": ["ใช้เงินตามใจ ชอบซื้อประสบการณ์", "หาเงินมาก็ใช้ให้มีความสุข", "ไม่ค่อยเก็บเงิน ชอบช้อปปิ้ง"],
    },
    "pets": {
        "pet_lover": ["รักสัตว์ อยากเลี้ยงหมาแมว", "มีแมวที่บ้าน เป็นทาสแมว", "ชอบสัตว์เลี้ยงมาก"],
        "no_pets": ["แพ้ขนสัตว์ ไม่เลี้ยงสัตว์", "ไม่ถนัดกับสัตว์เลี้ยง", "ไม่อยากมีสัตว์ในบ้าน"],
    },
}
P_MENTION = 0.75        # ค่านิยมของตัวเองที่ถูกพูดถึงในแชท (ที่เหลือระบบไม่รู้)


def make_values(rng) -> dict:
    """ค่านิยมจริง + มิติที่ผู้ใช้ "ใส่ใจ" ว่าคู่ต้องตรงกัน"""
    truth = {dim: rng.choice(sorted(opts)) for dim, opts in VALUES.items()}
    cares = rng.sample(sorted(VALUES), k=rng.randint(1, 3))
    return {"truth": truth, "cares": cares}


def self_text(values, rng) -> str:
    said = [rng.choice(VALUES[d][v]) for d, v in values["truth"].items() if rng.random() < P_MENTION]
    return " ".join(said)


def want_text(values, rng) -> str:
    return " ".join(rng.choice(VALUES[d][values["truth"][d]]) for d in values["cares"])


def score(a_values, b_values) -> float:
    """สัดส่วนมิติที่ A ใส่ใจและ B ตรงกัน"""
    cares = a_values["cares"]
    return sum(a_values["truth"][d] == b_values["truth"][d] for d in cares) / len(cares) if cares else 0.0
