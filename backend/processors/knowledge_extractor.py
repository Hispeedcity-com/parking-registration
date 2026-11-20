"""
knowledge_extractor.py

Extracts useful knowledge from WhatsApp conversations.
"""

import re

# Messages that add no value to the knowledge base
IGNORE_PATTERNS = [
    r"^hi$",
    r"^hello$",
    r"^okay$",
    r"^ok$",
    r"^thanks?$",
    r"^thank you$",
    r"^noted$",
    r"^good morning$",
    r"^good afternoon$",
    r"^bye$"
]

# Phrases that indicate an outdated process
OBSOLETE_PATTERNS = [
    "registration form",
    "email us",
    "fill the form",
    "send the form",
    "attached form"
]


def clean_message(text):
    """Remove extra spaces."""
    return " ".join(str(text).split())


def is_ignored(text):
    """Check if message is just a greeting or short acknowledgement."""
    text = clean_message(text).lower()

    for pattern in IGNORE_PATTERNS:
        if re.fullmatch(pattern, text):
            return True

    return False


def is_obsolete(text):
    """Detect messages referring to old procedures."""
    text = clean_message(text).lower()

    for phrase in OBSOLETE_PATTERNS:
        if phrase in text:
            return True

    return False


def remove_personal_information(text):
    """Mask common personal information."""

    # Phone numbers
    text = re.sub(r"\+?\d[\d\-\s]{7,}", "[PHONE]", text)

    # Vehicle plate (simple heuristic)
    text = re.sub(r"\b[A-Z]{1,3}\d{1,4}[A-Z]?\b", "[PLATE]", text)

    return text


def extract_knowledge(conversation):
    """
    Extract useful messages from one conversation.
    """

    knowledge = []

    for line in conversation.split("\n"):

        line = clean_message(line)

        if not line:
            continue

        if is_ignored(line):
            continue

        if is_obsolete(line):
            continue

        line = remove_personal_information(line)

        knowledge.append(line)

    return knowledge