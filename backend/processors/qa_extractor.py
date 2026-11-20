"""
qa_extractor.py

Extract Question-Answer pairs from WhatsApp conversations.
"""

import re


QUESTION_WORDS = (
    "how",
    "what",
    "where",
    "when",
    "why",
    "can",
    "is",
    "do",
    "does",
    "which",
    "who"
)


def is_question(text):
    """
    Detect whether a message is likely a question.
    """

    text = str(text).strip().lower()

    if text.endswith("?"):
        return True

    for word in QUESTION_WORDS:
        if text.startswith(word + " "):
            return True

    return False


def build_pairs(messages):
    """
    Pair a customer question with the next staff reply.
    """

    pairs = []

    current_question = None

    for sender, message in messages:

        message = str(message).strip()

        if is_question(message):

            current_question = message

            continue

        if current_question:

            pairs.append({

                "question": current_question,

                "answer": message

            })

            current_question = None

    return pairs