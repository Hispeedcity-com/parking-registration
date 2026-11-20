"""
Keyword Search

Improved retrieval for the HispeedCity knowledge base.

The search combines:
1. Keyword overlap
2. Question similarity
3. Answer similarity
4. Important parking-domain keywords
5. Exact phrase matching
"""

import re
from difflib import SequenceMatcher

from retrieval.search_result import SearchResult


class KeywordSearch:

    def __init__(self, knowledge_records):

        self.records = knowledge_records

        # Important words in the HispeedCity domain.
        # These receive additional weight during retrieval.
        self.domain_keywords = {
            "register",
            "registration",
            "regist",
            "renew",
            "renewal",
            "renewed",
            "deregister",
            "deregistration",
            "cancel",
            "parking",
            "season",
            "monthly",
            "barrier",
            "gate",
            "exit",
            "enter",
            "entry",
            "plate",
            "number",
            "vehicle",
            "car",
            "anpr",
            "camera",
            "expired",
            "expire",
            "expiry",
            "valid",
            "active",
            "status",
            "payment",
            "pay",
            "receipt",
            "price",
            "pricing",
            "fee",
            "cost",
        }

    # =====================================================
    # Normalize text
    # =====================================================

    def normalize(self, text):

        text = str(text).lower()

        # Remove punctuation
        text = re.sub(r"[^\w\s]", " ", text)

        # Remove extra spaces
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    # =====================================================
    # Get words
    # =====================================================

    def get_words(self, text):

        text = self.normalize(text)

        return set(text.split())

    # =====================================================
    # Remove common words
    # =====================================================

    def useful_words(self, text):

        stop_words = {
            "a",
            "an",
            "the",
            "is",
            "are",
            "am",
            "i",
            "me",
            "my",
            "you",
            "your",
            "we",
            "our",
            "how",
            "do",
            "does",
            "can",
            "could",
            "would",
            "what",
            "when",
            "where",
            "why",
            "to",
            "for",
            "of",
            "on",
            "in",
            "at",
            "and",
            "or",
            "please",
            "want",
            "need",
        }

        words = self.get_words(text)

        return words - stop_words

    # =====================================================
    # Keyword overlap
    # =====================================================

    def keyword_score(self, query, text):

        query_words = self.useful_words(query)
        text_words = self.useful_words(text)

        if not query_words or not text_words:
            return 0.0

        common_words = query_words.intersection(text_words)

        return len(common_words) / len(query_words)

    # =====================================================
    # Domain keyword score
    # =====================================================

    def domain_score(self, query, text):

        query_words = self.get_words(query)
        text_words = self.get_words(text)

        query_domain_words = (
            query_words.intersection(self.domain_keywords)
        )

        if not query_domain_words:
            return 0.0

        matched = (
            query_domain_words.intersection(text_words)
        )

        return len(matched) / len(query_domain_words)

    # =====================================================
    # Sequence similarity
    # =====================================================

    def similarity(self, a, b):

        return SequenceMatcher(
            None,
            self.normalize(a),
            self.normalize(b)
        ).ratio()

    # =====================================================
    # Phrase matching
    # =====================================================

    def phrase_bonus(self, query, text):

        query_normalized = self.normalize(query)
        text_normalized = self.normalize(text)

        if not query_normalized or not text_normalized:
            return 0.0

        # Exact question
        if query_normalized == text_normalized:
            return 0.30

        # Query appears inside the text
        if query_normalized in text_normalized:
            return 0.20

        # Text appears inside query
        if text_normalized in query_normalized:
            return 0.15

        return 0.0

    # =====================================================
    # Special concept matching
    # =====================================================

    def concept_bonus(self, query, text):

        query_words = self.get_words(query)
        text_words = self.get_words(text)

        bonus = 0.0

        # -------------------------------------------------
        # Barrier / exit / entry
        # -------------------------------------------------

        barrier_words = {
            "barrier",
            "gate",
            "exit",
            "entry",
            "enter",
            "cannot",
            "unable",
            "open",
        }

        if query_words.intersection(barrier_words):

            if text_words.intersection({
                "barrier",
                "gate",
                "exit",
                "entry",
                "camera",
                "plate",
                "parking",
            }):
                bonus += 0.15

        # -------------------------------------------------
        # Registration
        # -------------------------------------------------

        registration_words = {
            "register",
            "registration",
            "regist",
            "apply",
        }

        if query_words.intersection(registration_words):

            if text_words.intersection({
                "register",
                "registration",
                "apply",
                "vehicle",
                "parking",
            }):
                bonus += 0.15

        # -------------------------------------------------
        # Renewal
        # -------------------------------------------------

        renewal_words = {
            "renew",
            "renewal",
            "renewed",
            "extend",
            "expired",
            "expire",
        }

        if query_words.intersection(renewal_words):

            if text_words.intersection({
                "renew",
                "renewal",
                "expired",
                "expire",
                "subscription",
                "parking",
            }):
                bonus += 0.15

        # -------------------------------------------------
        # Deregistration
        # -------------------------------------------------

        deregistration_words = {
            "deregister",
            "deregistration",
            "cancel",
            "terminate",
            "remove",
        }

        if query_words.intersection(deregistration_words):

            if text_words.intersection({
                "deregister",
                "deregistration",
                "cancel",
                "terminate",
                "remove",
            }):
                bonus += 0.20

        # -------------------------------------------------
        # ANPR / plate
        # -------------------------------------------------

        anpr_words = {
            "anpr",
            "plate",
            "camera",
            "recognized",
            "recognize",
            "detected",
            "detect",
        }

        if query_words.intersection(anpr_words):

            if text_words.intersection({
                "anpr",
                "plate",
                "camera",
                "recognized",
                "recognize",
                "detected",
                "detect",
            }):
                bonus += 0.15

        # -------------------------------------------------
        # Pricing
        # -------------------------------------------------

        pricing_words = {
            "price",
            "pricing",
            "fee",
            "fees",
            "cost",
            "rate",
            "rates",
            "much",
        }

        if query_words.intersection(pricing_words):

            if text_words.intersection({
                "price",
                "pricing",
                "fee",
                "fees",
                "cost",
                "rate",
                "rates",
                "rm",
                "monthly",
            }):
                bonus += 0.15

        # -------------------------------------------------
        # Payment
        # -------------------------------------------------

        payment_words = {
            "pay",
            "payment",
            "receipt",
            "invoice",
            "bank",
        }

        if query_words.intersection(payment_words):

            if text_words.intersection({
                "pay",
                "payment",
                "receipt",
                "invoice",
                "bank",
            }):
                bonus += 0.15

        return bonus

    # =====================================================
    # Calculate final score
    # =====================================================

    def calculate_score(self, query, record):

        question = record.question
        answer = record.answer

        # -------------------------------------------------
        # Similarity
        # -------------------------------------------------

        question_similarity = self.similarity(
            query,
            question
        )

        answer_similarity = self.similarity(
            query,
            answer
        )

        # -------------------------------------------------
        # Keyword scores
        # -------------------------------------------------

        question_keywords = self.keyword_score(
            query,
            question
        )

        answer_keywords = self.keyword_score(
            query,
            answer
        )

        # -------------------------------------------------
        # Domain score
        # -------------------------------------------------

        domain_question = self.domain_score(
            query,
            question
        )

        # -------------------------------------------------
        # Bonuses
        # -------------------------------------------------

        phrase_bonus = self.phrase_bonus(
            query,
            question
        )

        concept_bonus = self.concept_bonus(
            query,
            question
        )

        # -------------------------------------------------
        # Final score
        # -------------------------------------------------

        score = (
            question_similarity * 0.25
            + answer_similarity * 0.05
            + question_keywords * 0.35
            + answer_keywords * 0.05
            + domain_question * 0.15
            + phrase_bonus
            + concept_bonus
        )

        # Keep score between 0 and 1
        score = min(score, 1.0)

        return score

    # =====================================================
    # Search
    # =====================================================

    def search(self, query, top_k=5):

        results = []

        for record in self.records:

            score = self.calculate_score(
                query,
                record
            )

            results.append(
                SearchResult(
                    knowledge=record,
                    score=score
                )
            )

        # Highest score first
        results.sort(
            key=lambda x: x.score,
            reverse=True
        )

        return results[:top_k]