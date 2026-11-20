"""
conversation_loader.py

Builds one conversation document
from each WhatsApp chat.
"""

from pathlib import Path
import pandas as pd

from models.document import Document

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FILE = PROJECT_ROOT / "data" / "processed" / "whatsapp_messages.csv"


class ConversationLoader:

    def load(self):

        df = pd.read_csv(FILE)

        documents = []

        grouped = df.groupby("file")

        for filename, group in grouped:

            conversation = ""

            for _, row in group.iterrows():

                conversation += (
                    f"{row['sender']}:\n"
                    f"{row['message']}\n\n"
                )

            documents.append(

                Document(

                    id=filename,

                    source="WhatsApp",

                    title=filename,

                    content=conversation,

                    metadata={
                        "messages": len(group)
                    }

                )

            )

        print(f"Loaded {len(documents)} conversations")

        return documents