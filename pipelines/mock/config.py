"""ค่าคงที่ของ mock dataset: archetype, สัดส่วน, template ข้อความ"""
from datetime import date

from ..common import taxonomy

TODAY = date(2026, 9, 25)

LABEL = taxonomy.labels()
ALIASES = taxonomy.aliases()
HOBBIES = taxonomy.ids("hobbies")
RED_FLAGS = taxonomy.ids("red_flags")
LOVE_LANGS = taxonomy.ids("love_languages")
ALL_TRAITS = taxonomy.ids("traits")


FACULTIES = ["วิศวกรรมศาสตร์", "วิทยาศาสตร์", "แพทยศาสตร์", "พยาบาลศาสตร์", "วิทยาการจัดการ",
             "ศิลปศาสตร์", "นิติศาสตร์", "เภสัชศาสตร์", "ทันตแพทยศาสตร์", "เศรษฐศาสตร์", "การแพทย์แผนไทย"]


NICKNAMES = ["นนท์", "แพรว", "ต้น", "มายด์", "บอส", "ฝน", "เจ", "ปอ", "มิ้นท์", "กัน", "ใบเตย", "ภูมิ", "ออม",
             "ฟ้า", "ไอซ์", "เฟิร์น", "พีท", "น้ำ", "โอ๊ต", "แนน", "บีม", "จูน", "เก่ง", "ขวัญ", "ตาล", "ปาล์ม"]


# สัดส่วนอ้างอิงภาพรวมงานวิจัย attachment (secure มากสุด)
ATTACH_DIST = [("attach:secure", 0.50), ("attach:anxious", 0.22), ("attach:avoidant", 0.18), ("attach:fearful", 0.10)]


# archetype กำหนดความสอดคล้องภายในของ persona -> ข้อมูลไม่สุ่มมั่ว
ARCHETYPES = {
    "quiet_home": {"traits": ["trait:introvert", "trait:calm", "trait:homebody"], "hobbies": ["hobby:cooking", "hobby:lofi_music", "hobby:reading", "hobby:movies", "hobby:baking", "hobby:pets", "hobby:drawing"], "sleep": ["late", "normal"], "weekend": "stay_home", "social": "low"},
    "social_butterfly": {"traits": ["trait:extrovert", "trait:funny", "trait:spontaneous"], "hobbies": ["hobby:party", "hobby:concert", "hobby:cafe", "hobby:travel", "hobby:football"], "sleep": ["late"], "weekend": "go_out", "social": "high"},
    "active_outdoor": {"traits": ["trait:adventurous", "trait:responsible", "trait:extrovert"], "hobbies": ["hobby:hiking", "hobby:running", "hobby:gym", "hobby:travel", "hobby:photography"], "sleep": ["early"], "weekend": "outdoor", "social": "mid"},
    "creative": {"traits": ["trait:introvert", "trait:emotional", "trait:adventurous"], "hobbies": ["hobby:drawing", "hobby:photography", "hobby:cafe", "hobby:lofi_music", "hobby:movies"], "sleep": ["late"], "weekend": "cafe", "social": "mid"},
    "achiever": {"traits": ["trait:ambitious", "trait:responsible", "trait:logical"], "hobbies": ["hobby:gym", "hobby:reading", "hobby:running", "hobby:volunteer", "hobby:cafe"], "sleep": ["early", "normal"], "weekend": "self_improve", "social": "mid"},
    "gamer_chill": {"traits": ["trait:homebody", "trait:funny", "trait:logical"], "hobbies": ["hobby:gaming", "hobby:movies", "hobby:lofi_music", "hobby:football"], "sleep": ["late"], "weekend": "stay_home", "social": "low"},
}


BREAKUP_TEMPLATES = [
    "คนที่แนะนำมาไม่ไหวอะ ขอเลิกคุยนะ {r}",
    "เลิกคุยแล้วนะ รู้สึกไม่โอเค {r}",
    "ไม่ไปต่อละ {r} แบบนี้ไม่ใช่เลย",
    "ขอผ่านคนนี้ {r} เหนื่อยใจ",
]


CHAT_OPENERS = ["วันนี้เหนื่อยมากเลย", "เพิ่งเลิกเรียน", "ว่างๆ เลยมาคุยด้วย", "วันนี้ชิลๆ", "สอบเสร็จแล้วเย้"]
