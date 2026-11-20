from dataclasses import dataclass
from models.knowledge import Knowledge


@dataclass
class SearchResult:
    knowledge: Knowledge
    score: float