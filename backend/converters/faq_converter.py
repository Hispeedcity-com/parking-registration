
"""
faq_converter.py

Convert FAQ Documents into Knowledge objects.
"""

from models.knowledge import Knowledge


class FAQConverter:

    def convert(self, documents):

        knowledge = []

        for doc in documents:

            record = Knowledge(

                id=doc.id,

                category=doc.metadata.get("category", "General"),

                question=doc.title,

                answer=doc.content,

                source="FAQ",

                status="Active",

                confidence=1.0,

                metadata=doc.metadata

            )

            knowledge.append(record)

        print(f"Converted {len(knowledge)} FAQ records")

        return knowledge
