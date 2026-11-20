"""
conversation_cleaner.py

Cleans WhatsApp messages before they are used
to build the AI knowledge base.
"""

import re
from utils.constants import REMOVE_MESSAGES


def normalize(text):
    """
    Normalize text by:
    - converting to lowercase
    - removing punctuation
    - removing extra spaces
    """

    text = str(text).lower()

    # Remove punctuation
    text = re.sub(r"[^\w\s]", "", text)

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def clean_messages(df):
    """
    Remove greetings, media, empty messages,
    and very short messages.
    """

    print("\nCleaning WhatsApp messages...")

    # Remove rows with missing messages
    df = df.dropna(subset=["message"])

    # Convert message column to string
    df["message"] = df["message"].astype(str)

    # Remove leading/trailing spaces
    df["message"] = df["message"].str.strip()

    # Normalize messages
    normalized = df["message"].apply(normalize)

    # Remove greetings and useless messages
    df = df[~normalized.isin(REMOVE_MESSAGES)]

    # Remove messages shorter than 3 characters
    df = df[df["message"].str.len() > 2]

    print(f"Remaining messages: {len(df)}")

    return df