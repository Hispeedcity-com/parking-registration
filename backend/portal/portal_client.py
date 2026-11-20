"""
HispeedCity Portal Client

Communicates with the HispeedCity portal API to retrieve live customer parking information.
Supports lookup by vehicle plate or by reference number (SP-XXXX-XXXXXX / RN-XXXX-XXXXXX).
"""

import os
from pathlib import Path
import pandas as pd
import requests


class PortalClient:

    def __init__(self):
        # Project root
        self.project_root = Path(__file__).resolve().parents[1]

        # Live Portal API URL (default: local portal backend at http://localhost:8000/api)
        self.api_base_url = os.getenv(
            "PORTAL_API_URL",
            f"http://127.0.0.1:{os.getenv('PORT', '8080')}/api",
        )

        # Optional local CSV file fallback (legacy)
        self.customer_file = self.project_root / "data" / "portal" / "customers.csv"
        self.customers_df = None
        if self.customer_file.exists():
            try:
                df = pd.read_csv(self.customer_file)
                df["vehicle_plate"] = df["vehicle_plate"].astype(str).str.upper().str.replace(" ", "", regex=False)
                self.customers_df = df
            except Exception:
                self.customers_df = None

    # =========================================================
    # Lookup by Vehicle Plate
    # =========================================================

    def get_parking_status(self, vehicle_plate):
        """
        Retrieves vehicle parking status.
        Queries live Portal API first; falls back to local CSV if API is unreachable.
        Normalises validity_period from renewalMonthNote for expiry display.
        """
        if not vehicle_plate:
            return {"found": False, "message": "No vehicle plate provided."}

        plate = str(vehicle_plate).upper().replace(" ", "").strip()

        # Step 1: Try Live Portal API
        try:
            url = f"{self.api_base_url.rstrip('/')}/parking/status/{plate}"
            response = requests.get(url, timeout=4.0)
            if response.status_code == 200:
                data = response.json()
                if "found" in data:
                    return self._normalise_response(data)
        except Exception:
            pass  # Fall back to local storage if API is not running

        # Step 2: Local CSV Fallback
        if self.customers_df is not None:
            matches = self.customers_df[self.customers_df["vehicle_plate"] == plate]
            if not matches.empty:
                customer = matches.iloc[0].to_dict()
                return {
                    "found": True,
                    "vehicle_plate": plate,
                    "customer_name": customer.get("name", "Customer"),
                    "parking_type": customer.get("parking_type", "Season Parking"),
                    "status": customer.get("status", "Active"),
                    "validity_period": customer.get("expiry_date", "end of subscription period"),
                    "expiry_date": customer.get("expiry_date", "end of subscription period"),
                    "payment_status": customer.get("payment_status", "Paid"),
                    "reference_number": customer.get("customer_id", ""),
                }

        # Step 3: Not Found
        return {
            "found": False,
            "vehicle_plate": plate,
            "message": f"No parking record was found for vehicle plate {plate}."
        }

    # =========================================================
    # Lookup by Reference Number
    # =========================================================

    def get_status_by_reference(self, ref_number):
        """
        Looks up a parking record by reference number (SP-XXXX-XXXXXX or RN-XXXX-XXXXXX).
        Returns the customer name, status, plates, and validity period.
        """
        if not ref_number:
            return {"found": False, "message": "No reference number provided."}

        ref = str(ref_number).strip().upper()

        try:
            url = f"{self.api_base_url.rstrip('/')}/parking/status/reference/{ref}"
            response = requests.get(url, timeout=4.0)
            if response.status_code == 200:
                data = response.json()
                if "found" in data:
                    return self._normalise_response(data)
        except Exception:
            pass

        return {
            "found": False,
            "reference_number": ref,
            "message": f"No parking record was found for reference number {ref}."
        }

    # =========================================================
    # Helpers
    # =========================================================

    def _normalise_response(self, data):
        """Ensures validity_period is always present (falls back to expiry_date)."""
        if data.get("found"):
            vp = data.get("validity_period") or data.get("expiry_date") or "end of subscription period"
            data["validity_period"] = vp
            data["expiry_date"] = vp
        return data

    def is_parking_active(self, vehicle_plate):
        status = self.get_parking_status(vehicle_plate)
        return status.get("found", False) and str(status.get("status", "")).lower() in ("active", "approved")