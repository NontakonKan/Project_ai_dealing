"""Retriever ชั่วคราว (placeholder) ให้ส่วน LLM ทดสอบได้ก่อน — ส่วน 2/3/4 แทนที่ด้วยของจริงที่ทำตาม contract เดียวกัน"""
from .dense_stub import DenseStub
from .graph_stub import GraphStub
from .hybrid_stub import HybridStub

__all__ = ["DenseStub", "GraphStub", "HybridStub"]
