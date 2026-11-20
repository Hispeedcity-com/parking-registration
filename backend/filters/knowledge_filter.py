"""
Knowledge Filter

Filters knowledge records based on
the detected customer intent.
"""


class KnowledgeFilter:

    def filter(self, knowledge_records, intent):

        # -------------------------------------------------
        # General questions
        # -------------------------------------------------

        if intent == "general":

            return knowledge_records

        filtered = []

        # -------------------------------------------------
        # Check each knowledge record
        # -------------------------------------------------

        for record in knowledge_records:

            category = record.category.lower()

            # ---------------------------------------------
            # Registration
            # ---------------------------------------------

            if intent == "registration":

                if category == "registration":

                    filtered.append(record)

            # ---------------------------------------------
            # Renewal
            # ---------------------------------------------

            elif intent == "renewal":

                if category == "renewal":

                    filtered.append(record)

            # ---------------------------------------------
            # Deregistration
            # ---------------------------------------------

            elif intent == "deregistration":

                if category == "deregistration":

                    filtered.append(record)

            # ---------------------------------------------
            # Payment
            # ---------------------------------------------

            elif intent == "payment":

                if category == "payment":

                    filtered.append(record)

            # ---------------------------------------------
            # Pricing
            # ---------------------------------------------

            elif intent == "pricing":

                if category == "pricing":

                    filtered.append(record)

            # ---------------------------------------------
            # Parking information, types, and policies
            # ---------------------------------------------

            elif intent == "parking_information":

                if category in [
                    "parking",
                    "parking types",
                    "parking policy",
                    "company policy",
                    "rules",
                    "pricing",
                    "location",
                    "access",
                ]:

                    filtered.append(record)

            # ---------------------------------------------
            # Barrier
            # ---------------------------------------------

            elif intent == "barrier":

                if category == "technical":

                    filtered.append(record)

            # ---------------------------------------------
            # ANPR
            # ---------------------------------------------

            elif intent == "anpr":

                if category == "technical":

                    filtered.append(record)

            # ---------------------------------------------
            # Parking Status
            # ---------------------------------------------
            # Until the portal API exists, use Technical
            # and Access information as supporting knowledge.
            # ---------------------------------------------

            elif intent == "parking_status":

                if category in [
                    "technical",
                    "access",
                    "renewal"
                ]:

                    filtered.append(record)

        # -------------------------------------------------
        # Safety fallback
        # -------------------------------------------------
        # If filtering produces nothing, search the entire
        # knowledge base instead of returning no answer.
        # -------------------------------------------------

        if len(filtered) == 0:

            return knowledge_records

        return filtered
