"""
priorities.py

Defines source priority for the knowledge base.
"""

SOURCE_PRIORITY = {
    "Portal": 100,
    "FAQ": 90,
    "Document": 80,
    "WhatsApp": 60,
    "Archive": 20
}


def get_priority(source):
    """
    Return priority score for a knowledge source.
    """
    return SOURCE_PRIORITY.get(source, 0)