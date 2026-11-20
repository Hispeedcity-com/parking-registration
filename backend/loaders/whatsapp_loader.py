"""
whatsapp_loader.py

Loads processed WhatsApp messages into Document objects.
"""

from pathlib import Path
import pandas as pd

from models.document import Document


PROJECT_ROOT = Path(__file__).resolve().parents[2]

WHATSAPP_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "whatsapp_messages.csv"
)


class WhatsAppLoader:

    def load(self):

        print("Loading WhatsApp messages...")

        df = pd.read_csv(WHATSAPP_FILE)

        documents = []

        for index, row in df.iterrows():

            documents.append(

                Document(

                    id=f"WA{index+1:05}",

                    source="WhatsApp",

                    title=f"Message from {row['sender']}",

                    content=row["message"],

                    metadata={

                        "conversation": row["file"],

                        "date": row["date"],

                        "sender": row["sender"]

                    }

                )

            )

        print(f"Loaded {len(documents)} WhatsApp documents")

        return documents