"""
HispeedCity AI Assistant

Flow:

User Question
      ↓
Reference Number Detected? → Portal lookup by ref → Return result
      ↓ (no)
Intent Detector
      ↓
Vehicle Plate Extracted?
      ↓ Yes → Portal lookup by plate (status / barrier / anpr)
      ↓ No  → Ask for plate (if intent needs it)
      ↓
Knowledge Filter → Keyword Search → Response Generator
"""

import re

from backend.loaders.faq_loader import FAQLoader
from backend.converters.faq_converter import FAQConverter
from backend.retrieval.keyword_search import KeywordSearch
from backend.intents.detector import IntentDetector
from backend.filters.knowledge_filter import KnowledgeFilter
from backend.generator.response_generator import ResponseGenerator
from backend.portal.portal_service import PortalService
from backend.utils.plate_extractor import VehiclePlateExtractor


# Pattern for reference numbers: SP-2026-000001 or RN-2026-000001
_REF_PATTERN = re.compile(
    r'\b((?:SP|RN)-\d{4}-\d{4,6})\b',
    re.IGNORECASE
)


class ChatBot:

    def __init__(self):

        print("Loading Knowledge Base...")

        loader = FAQLoader()
        docs = loader.load()

        converter = FAQConverter()
        self.knowledge = converter.convert(docs)

        self.intent_detector = IntentDetector()
        self.knowledge_filter = KnowledgeFilter()
        self.generator = ResponseGenerator()
        self.portal_service = PortalService()
        self.plate_extractor = VehiclePlateExtractor()

        print(f"{len(self.knowledge)} knowledge records loaded.")

    # =========================================================
    # Ask the chatbot
    # =========================================================

    def ask(self, question, context=None):
        """
        Process a user question and return a response dict.

        Args:
            question: The user's message string
            context:  Optional session dict carrying {vehicle_plate, intent, customer_name}
                      from previous turns (for multi-turn memory).

        Returns dict with keys: answer, intent, confidence, and optionally
            vehicle_plate, reference_number, portal_status, requires_plate.
        """

        # -------------------------------------------------
        # Step 1: Check for Reference Number first
        # (highest priority — user is giving us a specific ref)
        # -------------------------------------------------

        ref_match = _REF_PATTERN.search(question)
        if ref_match:
            ref_number = ref_match.group(1).upper()
            portal_res = self.portal_service.check_by_reference(ref_number)
            return {
                "answer": portal_res["message"],
                "intent": "reference_lookup",
                "confidence": 1.0,
                "reference_number": ref_number,
                "portal_status": portal_res.get("status"),
            }

        # -------------------------------------------------
        # Step 2: Detect Intent & Extract Plate
        # -------------------------------------------------

        intent = self.intent_detector.detect(question)
        vehicle_plate = self.plate_extractor.extract(question)

        # If no plate in this message, try to inherit from session context
        if not vehicle_plate and context and context.get("vehicle_plate"):
            # Only carry plate forward for portal-relevant intents
            if intent in ("parking_status", "barrier", "anpr", "general"):
                vehicle_plate = context["vehicle_plate"]

        # -------------------------------------------------
        # Step 3: Handle Portal / Transactional Intents
        # -------------------------------------------------

        if vehicle_plate:
            if intent in ("parking_status", "general"):
                portal_res = self.portal_service.check_parking(vehicle_plate)
                return {
                    "answer": portal_res["message"],
                    "intent": "parking_status",
                    "confidence": 1.0,
                    "vehicle_plate": vehicle_plate,
                    "portal_status": portal_res.get("status"),
                }

            if intent == "barrier":
                portal_res = self.portal_service.check_barrier(vehicle_plate)
                return {
                    "answer": portal_res["message"],
                    "intent": "barrier",
                    "confidence": 1.0,
                    "vehicle_plate": vehicle_plate,
                    "portal_status": portal_res.get("status"),
                }

            if intent == "anpr":
                portal_res = self.portal_service.check_anpr(vehicle_plate)
                return {
                    "answer": portal_res["message"],
                    "intent": "anpr",
                    "confidence": 1.0,
                    "vehicle_plate": vehicle_plate,
                    "portal_status": portal_res.get("status"),
                }

        # If intent requires portal but no plate yet — ask for it
        if intent in ("parking_status", "barrier", "anpr"):
            return {
                "answer": "May I have your vehicle plate number so I can check your parking status?",
                "intent": intent,
                "confidence": 1.0,
                "requires_plate": True,
            }

        # -------------------------------------------------
        # Step 4: Search filtered knowledge base (FAQ)
        # -------------------------------------------------

        filtered_knowledge = self.knowledge_filter.filter(self.knowledge, intent)
        search = KeywordSearch(filtered_knowledge)
        results = search.search(question, top_k=1)

        if not results:
            return {
                "answer": (
                    "Sorry, I couldn't find a suitable answer to your question. "
                    "Please contact HispeedCity customer support for assistance."
                ),
                "intent": intent,
                "confidence": 0.0,
            }

        best = results[0]
        answer = self.generator.generate(best, intent)

        return {
            "answer": answer,
            "intent": intent,
            "confidence": best.score,
        }