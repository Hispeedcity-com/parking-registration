"""
knowledge_manager.py

Loads all available knowledge sources into one list.
"""

from loaders.faq_loader import FAQLoader
from loaders.whatsapp_loader import WhatsAppLoader


class KnowledgeManager:

    def __init__(self):

        self.loaders = [

            FAQLoader(),

            WhatsAppLoader()

        ]

    def load_all(self):

        all_documents = []

        for loader in self.loaders:

            docs = loader.load()

            all_documents.extend(docs)

        print()

        print("=" * 60)

        print("Knowledge Summary")

        print("=" * 60)

        print(f"Total documents: {len(all_documents)}")

        return all_documents