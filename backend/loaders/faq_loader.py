"""
faq_loader.py

Loads processed FAQ data into Document objects.
"""

from pathlib import Path
import pandas as pd

from models.document import Document


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FAQ_FILE = PROJECT_ROOT / "data" / "processed" / "faq_clean.csv"


class FAQLoader:

    def load(self):

        print("Loading FAQ...")

        df = pd.read_csv(FAQ_FILE)

        documents = []

        for _, row in df.iterrows():

            documents.append(

                Document(

                    id=row["id"],

                    source="FAQ",

                    title=row["question"],

                    content=row["answer"],

                    metadata={

                        "category": row["category"],

                        "verified": row["verified"]

                    }

                )

            )

        print(f"Loaded {len(documents)} FAQ documents")

        return documents