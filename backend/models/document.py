"""
document.py

Defines the standard document model used throughout
the AI Assistant.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Document:
    id: str
    source: str
    title: str
    content: str
    metadata: Dict[str, Any]