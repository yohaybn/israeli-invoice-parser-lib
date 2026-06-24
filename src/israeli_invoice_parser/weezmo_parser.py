import json
import logging
import os
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs, urljoin
from typing import Dict, Any
from .base_parser import BaseReceiptParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WeezmoParser")

class WeezmoParser(BaseReceiptParser):
    def __init__(self) -> None:
        super().__init__(store_name="Weezmo Provider")

    def parse(self, source_data: str) -> Dict[str, Any]:
        raw_json: str = ""

        if source_data.startswith("http://") or source_data.startswith("https://"):
            try:
                base_url = source_data.strip()
                
                # Modern browser header signature matrix to prevent WAF socket hanging
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Connection': 'close' # Explicitly close the connection to prevent hanging sockets
                }

                parsed_url = urlparse(base_url)
                queries = parse_qs(parsed_url.query)
                
                receipt_token = queries.get("q", [None])[0]

                # If it's a short link (wee.ai), catch the 302 redirect location header
                if not receipt_token and "wee.ai" in base_url:
                    logger.info("Intercepting wee.ai short-link redirection matrix...")
                    
                    class InterceptRedirectHandler(urllib.request.HTTPRedirectHandler):
                        def http_error_302(self, req, fp, code, msg, headers):
                            return fp

                    # Build opener with low fallback timeouts
                    opener = urllib.request.build_opener(InterceptRedirectHandler())
                    req = urllib.request.Request(base_url, headers=headers)
                    
                    with opener.open(req, timeout=8) as response:
                        redirect_location = response.headers.get('Location', '')
                        if redirect_location:
                            # Safely handle both absolute and relative paths (/cms.html?q=...)
                            if not redirect_location.startswith('http'):
                                redirect_location = urljoin(base_url, redirect_location)
                                
                            logger.info(f"Redirection resolved to target landing: {redirect_location}")
                            parsed_redirect = urlparse(redirect_location)
                            redirect_queries = parse_qs(parsed_redirect.query)
                            receipt_token = redirect_queries.get("q", [None])[0]

                if not receipt_token:
                    raise ValueError("Could not extract a valid query token 'q' from the Weezmo link framework.")

                api_url = f"https://receipts.weezmo.com/api/receipts/{receipt_token}"
                logger.info(f"Targeting Weezmo data provider gateway: {api_url}")

                # Download the target stream with an explicit socket timeout trigger (10 seconds max)
                api_req = urllib.request.Request(api_url, headers=headers)
                with urllib.request.urlopen(api_req, timeout=10) as response:
                    raw_json = response.read().decode('utf-8')


            except urllib.error.HTTPError as http_err:
                logger.error(f"Weezmo engine connection exception: {http_err.code}")
                raise ValueError(f"שגיאת תקשורת מול שרת וויזמו: קוד {http_err.code}")
            except urllib.error.URLError as url_err:
                logger.error(f"Weezmo network timeout or unresolved destination: {url_err.reason}")
                raise ValueError("חיבור הרשת לשרת וויזמו נותק או הגיע למגבלת זמן (Timeout).")
            except Exception as e:
                logger.error(f"Critical execution error resolving Weezmo document: {e}")
                raise e
        else:
            raw_json = source_data

        try:
            if not raw_json.strip():
                raise ValueError("Payload data stream returned empty string bounds.")

            payload_data = json.loads(raw_json)
            if isinstance(payload_data, list):
                if len(payload_data) == 0:
                    raise ValueError("Weezmo data matrix array is empty.")
                payload = payload_data[0]
            else:
                payload = payload_data

            branch_info = payload.get("tBranch", {}) or {}
            business_info = payload.get("tBusiness", {}) or {}
            
            dynamic_store_name = business_info.get("businessName", branch_info.get("branchName", "רשת קמעונאות")).strip()
            self.store_name = dynamic_store_name
            logger.info(f"Dynamic branding identity successfully verified as: '{self.store_name}'")

            created_date = payload.get("createdDate", "2026-01-01T00:00:00Z")
            date_part, time_part = created_date.split("T") if "T" in created_date else (created_date, "00:00:00")
            if "-" in date_part:
                parts = date_part.split("-")
                formatted_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
            else:
                formatted_date = date_part

            payments_list = payload.get("payments", [])
            primary_payment = payments_list[0] if isinstance(payments_list, list) and len(payments_list) > 0 else {}

            unified_receipt: Dict[str, Any] = {
                "store_name": self.store_name,
                "pdf_url": f"https://receipts.weezmo.com/api/receipts/signed/{receipt_token}/download",
                "company_legal_id": str(branch_info.get("vatNumber", payload.get("businessID", "515136893"))),
                "branch_name": str(branch_info.get("branchName", "סניף כללי")).strip(),
                "store_address": str(branch_info.get("branchAddress", "")).strip(),
                "store_phone": str(business_info.get("phone", "")).strip() or str(branch_info.get("branchPhone", "")).strip(),
                "customer_name": str(payload.get("loyalName", "")).strip() or None,
                "date": formatted_date,
                "time": time_part[:8],
                "receipt_id": receipt_token,
                "total_paid": float(payload.get("total", 0.0)),
                "vat_rate": float(payload.get("vat", 17.0)),
                "total_vat_paid": float(payload.get("vatTotal", 0.0)),
                "payment_method": str(primary_payment.get("name", "אשראי")).strip(),
                "items": []
            }

            for item in payload.get("items", []):
                if not isinstance(item, dict):
                    continue

                quantity = float(item.get("quantity", 1.0))
                unit_price = float(item.get("price", 0.0))
                final_price = float(item.get("total", quantity * unit_price))
                expected_total = round(quantity * unit_price, 2)

                discount_amount = 0.0
                deal_description = ""
                additional_data = item.get("additionalData", [])
                
                if isinstance(additional_data, list):
                    for data_node in additional_data:
                        if isinstance(data_node, dict) and "value" in data_node:
                            val_str = str(data_node.get("value", ""))
                            if "-" in val_str:
                                try:
                                    discount_amount = abs(float(val_str))
                                    deal_description = str(data_node.get("key", "")).strip()
                                except ValueError:
                                    pass

                has_deal = True if (discount_amount > 0 or deal_description) else False
                is_weight = not quantity.is_integer()

                unified_receipt["items"].append({
                    "description": str(item.get("name", "פריט")).strip(),
                    "barcode": str(item.get("itemCode")) if item.get("itemCode") else None,
                    "is_by_weight": is_weight,
                    "quantity_or_weight": quantity,
                    "unit_price": unit_price,
                    "original_total_price": expected_total,
                    "is_part_of_deal": has_deal,
                    "deal_text": deal_description or None,
                    "discount_amount": discount_amount,
                    "final_price": final_price,
                    "category_path": ["ביגוד ואופנה"] if self.store_name == "H&O" else ["סופרמרקט"]
                })

            return unified_receipt

        except Exception as ex:
            logger.error(f"Error mapping Weezmo dynamic parameters: {ex}")