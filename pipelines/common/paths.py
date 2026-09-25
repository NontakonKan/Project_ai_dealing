"""ตำแหน่งไฟล์/โฟลเดอร์ที่ใช้ร่วมกันทุก pipeline"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
MOCK = DATA / "mock"
PROCESSED = DATA / "processed"
TAXONOMY_FILE = DATA / "taxonomy.json"
LEXICON_FILE = DATA / "concept_lexicon.json"
