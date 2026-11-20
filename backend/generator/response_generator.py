"""
response_generator.py

Generates the final chatbot response.
"""

PORTAL_URL = "https://www.hispeedcity.com/index.html"


class ResponseGenerator:

    def __init__(self):
        pass

    def generate(self, knowledge, intent=None):

        # -------------------------------------------------
        # SearchResult contains the actual Knowledge object
        # -------------------------------------------------

        if hasattr(knowledge, "knowledge"):
            knowledge = knowledge.knowledge

        # -------------------------------------------------
        # Get the knowledge information
        # -------------------------------------------------

        answer = knowledge.answer

        # -------------------------------------------------
        # REGISTRATION
        # -------------------------------------------------

        if intent == "registration":

            return f"""
{answer}

----------------------------------------

You can complete your registration through the official HispeedCity Portal.

Portal:
{PORTAL_URL}

After submitting your application, please wait for the confirmation email before using your parking.
""".strip()

        # -------------------------------------------------
        # RENEWAL
        # -------------------------------------------------

        if intent == "renewal":

            return f"""
{answer}

----------------------------------------

You can renew your season parking through the official HispeedCity Portal.

Portal:
{PORTAL_URL}

After completing your renewal, please wait for the confirmation email.
""".strip()

        # -------------------------------------------------
        # DEREGISTRATION
        # -------------------------------------------------

        if intent == "deregistration":

            return f"""
{answer}

----------------------------------------

You can submit your deregistration request through the official HispeedCity Portal.

Portal:
{PORTAL_URL}

Once submitted, your request will be processed by our team.
""".strip()

        # -------------------------------------------------
        # DEFAULT
        # -------------------------------------------------

        return answer