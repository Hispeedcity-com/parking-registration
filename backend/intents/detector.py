"""
Intent Detection Module

Detects what the customer wants before
searching the knowledge base using NLP fuzzy matching.
Supports both English and Malay.
"""

import re
from rapidfuzz import fuzz, process


class IntentDetector:

    def __init__(self):

        self.intents = {

            # -------------------------------------------------
            # Parking information / Jenis & peraturan parkir
            # -------------------------------------------------
            # Keep these questions separate from registration and renewal.
            # For example, "What is season parking?" is asking for a
            # definition, not asking to apply for a parking subscription.
            "parking_information": [
                "what is season parking", "what are season parking",
                "what is reserved parking", "what is non reserved parking",
                "what is non-reserved parking", "what is premium parking",
                "parking rules", "parking regulations", "parking policy",
                "rules and regulations of the parking facility",
            ],

            # -------------------------------------------------
            # Pricing / Harga
            # -------------------------------------------------

            "pricing": [
                "price", "pricing", "fee", "fees", "monthly fee", 
                "parking fee", "cost", "rate", "rates", "how much",
                "how much is parking", "how much does parking cost", "monthly price",
                "harga", "yuran", "berapa", "kos", "berapa harga", "bayaran bulanan"
            ],

            # -------------------------------------------------
            # Parking Status / Status Letak Kereta
            # -------------------------------------------------

            "parking_status": [
                "parking status", "status of my parking", "is my parking active",
                "is my parking valid", "is my parking still valid", "parking still active",
                "check my parking", "check parking status", "when does my parking expire",
                "when will my parking expire", "parking expiry", "expiry date",
                "status", "sah", "tamat tempoh", "bila tamat", "tarikh luput", "semak parking"
            ],

            # -------------------------------------------------
            # Barrier / Palang
            # -------------------------------------------------

            "barrier": [
                "barrier", "barrier won't open", "barrier will not open", "barrier not opening",
                "cannot enter", "can't enter", "cannot exit", "can't exit",
                "unable to enter", "unable to exit", "cannot get out", "cannot get in",
                "gate", "gate won't open", "boom gate",
                "palang", "tak boleh buka", "tak boleh keluar", "tak boleh masuk",
                "palang tak buka", "sangkar", "pagar"
            ],

            # -------------------------------------------------
            # ANPR / Kamera
            # -------------------------------------------------

            "anpr": [
                "anpr", "camera", "camera cannot detect", "camera can't detect",
                "camera not detecting", "license plate", "number plate", "car plate",
                "vehicle plate", "plate not detected", "plate not recognized",
                "kamera", "plat", "nombor plat", "tak cam", "kamera rosak", "plat tak detect"
            ],

            # -------------------------------------------------
            # Renewal / Perbaharui
            # -------------------------------------------------

            "renewal": [
                "renew", "renewal", "renwal", "renwe", "rebew",
                "renew my parking", "renew parking", "renew season parking",
                "extend parking", "extend my parking", "parking expired",
                "parking has expired", "expired parking", "about to expire", "expiring parking",
                "perbaharui", "sambung", "tambah", "lanjut", "renew parking"
            ],

            # -------------------------------------------------
            # Deregistration / Batal
            # -------------------------------------------------

            "deregistration": [
                "deregister", "deregistration", "de-register", "de registration",
                "cancel", "cancel parking", "cancel my parking", "terminate parking",
                "terminate my parking", "stop parking", "remove parking",
                "batal", "berhenti", "tamatkan", "batal parking"
            ],

            # -------------------------------------------------
            # Payment / Bayaran
            # -------------------------------------------------

            "payment": [
                "pay", "payment", "make payment", "payment method",
                "payment failed", "payment fail", "payment receipt", "receipt",
                "invoice", "bank", "bank account", "payment proof",
                "bayar", "bayaran", "resit", "bukti bayaran", "akaun bank"
            ],

            # -------------------------------------------------
            # Registration / Daftar
            # -------------------------------------------------

            "registration": [
                "register", "registration", "regist", "regster",
                "register my car", "register vehicle", "register parking",
                "apply parking", "apply for parking", "new parking",
                "season parking", "monthly parking", "get parking",
                "daftar", "mohon", "baru", "parking baru", "daftar kereta"
            ],
        }

    # =========================================================
    # Detect Intent
    # =========================================================

    def detect(self, question):

        text = question.lower().strip()

        # Definition and policy questions must take precedence over broader
        # workflow keywords such as "season parking" or "renew".  Without
        # this guard, fuzzy matching can classify a simple parking-type
        # question as a registration or renewal request.
        parking_information_patterns = [
            r"\bwhat\s+(?:is|are)\s+(?:a\s+)?(?:season|reserved|non[\s-]?reserved|premium)\s+parking\b",
            r"\b(?:parking\s+)?(?:rules?|regulations?|policy)\b",
        ]
        if any(re.search(pattern, text) for pattern in parking_information_patterns):
            return "parking_information"

        # 1. Exact or regex boundary match (highest priority)
        for intent, keywords in self.intents.items():
            for keyword in keywords:
                pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
                if re.search(pattern, text):
                    return intent

        # 2. Fuzzy Matching (fallback for typos or slight variations)
        # We check the partial ratio of the text against all keywords
        best_intent = "general"
        highest_score = 0
        
        for intent, keywords in self.intents.items():
            for keyword in keywords:
                # partial_ratio is good for finding the keyword inside the larger sentence text
                # We use a threshold of 85 to be confident it's a match and not just random letters
                score = fuzz.partial_ratio(keyword.lower(), text)
                if score > highest_score:
                    highest_score = score
                    best_intent = intent
                    
        if highest_score >= 85:
            return best_intent

        return "general"
