"""
knowledge.py

Knowledge record used by the AI assistant.
"""

from dataclasses import dataclass


@dataclass
class Knowledge:

    id: str

    category: str

    question: str

    answer: str

    source: str

    status: str = "Active"

    confidence: float = 1.0

    metadata: dict | None = None