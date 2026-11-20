"""
Portal Service

Provides higher-level parking checks for the chatbot.
Uses validity_period (from renewalMonthNote) as the expiry indicator.
"""

from portal.portal_client import PortalClient

PORTAL_URL = "https://www.hispeedcity.com/index.html"


class PortalService:

    def __init__(self):
        self.portal = PortalClient()

    # =========================================================
    # Check by Reference Number (SP-XXXX / RN-XXXX)
    # =========================================================

    def check_by_reference(self, ref_number):
        result = self.portal.get_status_by_reference(ref_number)

        if not result["found"]:
            return {
                "success": False,
                "status": "not_found",
                "message": (
                    f"I could not find any parking record for reference number {ref_number.upper()}. "
                    "Please double-check the reference number and try again."
                )
            }

        name = result.get("customer_name") or "Valued Customer"
        status_raw = str(result.get("status") or "").strip()
        is_active = status_raw.lower() in ("active", "approved")
        validity = result.get("validity_period") or result.get("expiry_date") or "end of subscription period"
        parking_type = result.get("parking_type") or "Season Parking"
        plates = result.get("vehicle_plates") or []
        plate_str = ", ".join(plates) if plates else "N/A"

        if is_active:
            return {
                "success": True,
                "status": "active",
                "message": (
                    f"Hi {name}! Your parking record for reference {ref_number.upper()} is Active. ✅\n"
                    f"Parking Type: {parking_type}\n"
                    f"Vehicle Plate(s): {plate_str}\n"
                    f"Valid for: {validity}\n"
                    f"Payment Status: {result.get('payment_status', 'Paid')}"
                )
            }

        return {
            "success": True,
            "status": status_raw.lower(),
            "message": (
                f"Hi {name}! Your parking record for reference {ref_number.upper()} has status: {status_raw}.\n"
                f"Parking Type: {parking_type}\n"
                f"Vehicle Plate(s): {plate_str}\n"
                f"Valid for: {validity}\n"
                "If you need help, please contact HispeedCity customer support."
            )
        }

    # =========================================================
    # Check parking status by plate
    # =========================================================

    def check_parking(self, vehicle_plate):
        result = self.portal.get_parking_status(vehicle_plate)

        if not result["found"]:
            return {
                "success": False,
                "status": "not_found",
                "message": (
                    f"I could not find a parking record for vehicle plate {vehicle_plate.upper()}. "
                    "Please ensure your vehicle is registered on the HispeedCity portal."
                )
            }

        status = str(result.get("status") or "").lower()
        validity = result.get("validity_period") or result.get("expiry_date") or "end of subscription period"
        name = result.get("customer_name") or "Valued Customer"
        parking_type = result.get("parking_type") or "Season Parking"

        if status in ("active", "approved"):
            return {
                "success": True,
                "status": "active",
                "vehicle_plate": result.get("vehicle_plate"),
                "expiry_date": validity,
                "message": (
                    f"Hi {name}! Your {parking_type} parking for plate "
                    f"{vehicle_plate.upper()} is currently active. ✅\n"
                    f"Valid for: {validity}\n"
                    f"Payment Status: {result.get('payment_status', 'Paid')}"
                )
            }

        if status == "pending":
            return {
                "success": True,
                "status": "pending",
                "message": (
                    f"Your parking application for plate {vehicle_plate.upper()} is currently Pending approval. ⏳\n"
                    "Please wait for the confirmation from HispeedCity. You will be notified by email once approved."
                )
            }

        if status == "rejected":
            return {
                "success": True,
                "status": "rejected",
                "message": (
                    f"Your parking application for plate {vehicle_plate.upper()} was Rejected. ❌\n"
                    f"Please contact HispeedCity customer support or re-apply via the portal: {PORTAL_URL}"
                )
            }

        return {
            "success": True,
            "status": status,
            "message": (
                f"Your parking status for plate {vehicle_plate.upper()} is: {result.get('status')}.\n"
                "Please contact HispeedCity customer support for assistance."
            )
        }

    # =========================================================
    # Check barrier problem by plate
    # =========================================================

    def check_barrier(self, vehicle_plate):
        result = self.portal.get_parking_status(vehicle_plate)

        if not result["found"]:
            return {
                "success": False,
                "status": "not_found",
                "message": (
                    f"I could not find a parking record for vehicle plate {vehicle_plate.upper()}. "
                    "The barrier requires an active registered record to open. "
                    "Please register your vehicle via the official HispeedCity portal."
                )
            }

        status = str(result.get("status") or "").lower()
        validity = result.get("validity_period") or result.get("expiry_date") or "end of subscription period"

        if status in ("active", "approved"):
            return {
                "success": True,
                "status": "active",
                "message": (
                    f"Your parking record for plate {vehicle_plate.upper()} is currently active "
                    f"and valid for: {validity}. ✅\n\n"
                    "If the barrier is still not opening, it may be a camera detection issue. "
                    "Please ensure your plate is clean and clearly visible, or contact our support team at the intercom."
                )
            }

        if status == "pending":
            return {
                "success": True,
                "status": "pending",
                "message": (
                    f"Your parking application for plate {vehicle_plate.upper()} is still Pending approval. ⏳\n"
                    "The barrier will only open once your parking is approved. "
                    "Please wait for the confirmation email."
                )
            }

        if status == "rejected":
            return {
                "success": True,
                "status": "rejected",
                "message": (
                    f"Your parking application for plate {vehicle_plate.upper()} was Rejected. ❌\n"
                    f"The barrier cannot open for rejected applications. Please re-apply at: {PORTAL_URL}"
                )
            }

        return {
            "success": True,
            "status": status,
            "message": (
                f"Your parking record was found for plate {vehicle_plate.upper()}, "
                f"but its current status is '{result.get('status')}'. "
                "Please contact HispeedCity customer support for assistance."
            )
        }

    # =========================================================
    # Check ANPR problem by plate
    # =========================================================

    def check_anpr(self, vehicle_plate):
        result = self.portal.get_parking_status(vehicle_plate)

        if not result["found"]:
            return {
                "success": False,
                "status": "not_found",
                "message": (
                    f"I could not find a parking record for vehicle plate {vehicle_plate.upper()}. "
                    "ANPR cannot grant access without an active registered record. "
                    "Please register your vehicle via the official HispeedCity portal."
                )
            }

        status = str(result.get("status") or "").lower()
        validity = result.get("validity_period") or result.get("expiry_date") or "end of subscription period"

        if status in ("active", "approved"):
            return {
                "success": True,
                "status": "active",
                "message": (
                    f"Your parking for plate {vehicle_plate.upper()} is active and valid for: {validity}. ✅\n\n"
                    "If the ANPR camera is failing to detect your number plate:\n"
                    "• Ensure your plate is clean and not obstructed\n"
                    "• Drive slowly towards the camera\n"
                    "• Use the intercom or contact support if the issue persists"
                )
            }

        return {
            "success": True,
            "status": status,
            "message": (
                f"Your parking status for plate {vehicle_plate.upper()} is '{result.get('status')}'. "
                "ANPR access requires an Active parking status. "
                "Please contact HispeedCity customer support for assistance."
            )
        }