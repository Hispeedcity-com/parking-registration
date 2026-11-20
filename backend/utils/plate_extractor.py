"""
Vehicle Plate Extractor

Extracts and normalizes vehicle license plate numbers from natural language input.
"""

import re


class VehiclePlateExtractor:

    def __init__(self):
        # 1. Explicit contextual pattern (e.g. "plate is ABC 1234", "plate number: WXY1234", "plate UNKNOWN123")
        self.context_pattern = re.compile(
            r'\b(?:plate|car|vehicle|no\.?|num|number|regist|registration|vrm)\b\s*(?:is|:|=)?\s*([A-Za-z0-9]{2,10}(?:\s+[A-Za-z0-9]{1,6})?)',
            re.IGNORECASE
        )



        # 2. Standalone pattern (e.g. "ABC1234 barrier won't open", "Is WXY 1234 valid?")
        self.standalone_pattern = re.compile(
            r'(?<![A-Za-z])([A-Za-z]{1,3}\s*\d{1,4}\s*[A-Za-z]?)(?![A-Za-z0-9])',
            re.IGNORECASE
        )


        # Words/tokens to ignore to prevent false positives
        self.ignore_list = {
            "ANPR", "FAQ", "NO", "CAR", "HUB", "VIP", "OK", "YES", "GATE", "ID", "PORTAL"
        }

    def extract(self, text):
        """
        Extracts vehicle plate string from user text query.
        Returns normalized plate string (e.g. 'ABC1234') or None if not found.
        """
        if not text or not isinstance(text, str):
            return None

        clean_text = text.strip()

        # Step 1: Try context pattern first
        context_match = self.context_pattern.search(clean_text)
        if context_match:
            candidate = context_match.group(1).strip()
            normalized = self._normalize_and_validate(candidate)
            if normalized:
                return normalized

        # Step 2: Search for standalone patterns
        for match in self.standalone_pattern.finditer(clean_text):
            candidate = match.group(1).strip()
            normalized = self._normalize_and_validate(candidate)
            if normalized:
                return normalized

        return None

    def _normalize_and_validate(self, candidate):
        """
        Normalizes plate string (removes internal spaces and upper-cases)
        and verifies it contains both letters and digits.
        """
        # Upper case and strip all spaces
        normalized = candidate.upper().replace(" ", "")

        # Must contain at least 1 letter and at least 1 digit
        has_letters = bool(re.search(r'[A-Z]', normalized))
        has_digits = bool(re.search(r'\d', normalized))

        if not (has_letters and has_digits):
            return None

        if normalized in self.ignore_list:
            return None

        # Length check (e.g. Malaysian plates are between 2 and 9 characters without spaces)
        if 2 <= len(normalized) <= 10:
            return normalized

        return None
