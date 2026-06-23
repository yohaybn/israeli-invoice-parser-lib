import json
import logging
import os
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any
from .base_parser import BaseReceiptParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PairzonParser")

class PairzonParser(BaseReceiptParser):
    def __init__(self) -> None:
        # Initialize with a flexible placeholder; we will dynamically 
        # override self.store_name based on the receipt's real corporate metadata.
        super().__init__(store_name="Pairzon Provider")

    def parse(self, source_data: str) -> Dict[str, Any]:
        raw_json: str = ""

        if source_data.startswith("http://") or source_data.startswith("https://"):
            try:
                parsed_url = urlparse(source_data.strip())
                queries = parse_qs(parsed_url.query)
                
                doc_id = queries.get("id", [None])[0]
                pin_id = queries.get("p", [None])[0]
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7'
                }
                
                # Custom handler to block automatic 302 jumps so we can catch short-links gracefully
                class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                    def http_error_302(self, req, fp, code, msg, headers):
                        return fp

                opener = urllib.request.build_opener(NoRedirectHandler())

                # 1. Coordinate Extraction (Direct Parameters vs Short-Link Token Routing)
                if doc_id and pin_id:
                    api_url = f"https://{parsed_url.netloc}/v1.0/documents/{doc_id}?p={pin_id}"
                else:
                    logger.info("Processing standard short-link sequence. Resolving internal payload routing...")
                    path_parts = [p for p in parsed_url.path.split('/') if p]
                    if len(path_parts) < 2:
                        raise ValueError("The provided Pairzon short-link route structure is invalid or missing paths.")
                    
                    prefix = path_parts[0]
                    token = path_parts[1]
                    
                    # Target Pairzon's centralized cross-brand mapping api
                    link_lookup_url = f"https://{parsed_url.netloc}/v1.0/links/{prefix}/{token}"
                    logger.info(f"Querying endpoint metadata resolver: {link_lookup_url}")
                    
                    lookup_req = urllib.request.Request(link_lookup_url, headers=headers)
                    try:
                        with urllib.request.urlopen(lookup_req, timeout=15) as lookup_res:
                            lookup_data = json.loads(lookup_res.read().decode('utf-8'))
                            if isinstance(lookup_data, dict) and "data" in lookup_data:
                                lookup_data = lookup_data["data"]
                            
                            doc_id = lookup_data.get("documentId") or lookup_data.get("id")
                            pin_id = lookup_data.get("prefix") or prefix
                    except Exception as e:
                        logger.warning(f"Metadata link API resolution dropped ({e}). Trying 302 header interception loop...")
                        
                        req = urllib.request.Request(source_data, headers=headers)
                        with opener.open(req, timeout=15) as response:
                            redirect_location = response.headers.get('Location', '')
                            if redirect_location:
                                parsed_redirect = urlparse(redirect_location)
                                redirect_queries = parse_qs(parsed_redirect.query)
                                doc_id = redirect_queries.get("id", [None])[0]
                                pin_id = redirect_queries.get("p", [None])[0]

                    if doc_id and pin_id:
                        api_url = f"https://{parsed_url.netloc}/v1.0/documents/{doc_id}?p={pin_id}"
                    else:
                        raise ValueError("Failed to extract backend parameters from token signature.")

                # 2. Complete Transaction JSON Fetch
                logger.info(f"Targeting active data stream gateway: {api_url}")
                data_req = urllib.request.Request(api_url, headers=headers)
                with urllib.request.urlopen(data_req, timeout=15) as response:
                    raw_json = response.read().decode('utf-8')
                    
                os.makedirs("temp", exist_ok=True)
                with open("temp/pairzon_generic_raw.json", "w", encoding="utf-8") as f:
                    f.write(raw_json)
                    
            except urllib.error.HTTPError as http_err:
                error_body = http_err.read().decode('utf-8', errors='ignore')[:500]
                logger.error(f"Pairzon backend connection returned error code ({http_err.code}). Payload: {error_body}")
                raise ValueError(f"שגיאת תקשורת מול שרת קבלות פיירזון: {http_err.code}")
            except Exception as e:
                logger.error(f"Critical execution error resolving Pairzon network document: {e}")
                raise e
        else:
            raw_json = source_data

        # 3. Dynamic Mapping & Extraction Grid
        try:
            if not raw_json.strip():
                raise ValueError("The resolved data stream payload came back empty.")
                
            payload = json.loads(raw_json)
            if isinstance(payload, dict) and "data" in payload:
                payload = payload["data"]

            # Dynamic Brand Identification
            store_info = payload.get("store", {}) or {}
            biz_info = store_info.get("business", {}) or {}
            
            # Extract brand name dynamically from business node or fallback to domain signatures
            dynamic_store_name = biz_info.get("name", store_info.get("name", "רשת קמעונאות")).strip()
            self.store_name = dynamic_store_name
            logger.info(f"Dynamic branding identity successfully verified as: '{self.store_name}'")

            # Standardize date segments
            created_date = payload.get("createdDate", "2026-01-01T00:00:00")
            date_part, time_part = created_date.split("T") if "T" in created_date else (created_date, "00:00:00")
            if "-" in date_part:
                parts = date_part.split("-")
                formatted_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
            else:
                formatted_date = date_part
            
            unified_receipt: Dict[str, Any] = {
                "store_name": self.store_name,
                "company_legal_id": str(biz_info.get("companyLeagalId", payload.get("businessID", "513461053"))),
                "branch_name": store_info.get("name", "סניף כללי").strip(),
                "store_address": store_info.get("address", "").strip() or biz_info.get("address", "").strip(),
                "store_phone": store_info.get("phone", "").strip() or biz_info.get("phone", "").strip(),
                "customer_name": payload.get("cashierName", "").strip() or None,
                "date": formatted_date,
                "time": time_part[:8],
                "receipt_id": str(payload.get("transactionID", payload.get("id", ""))),
                "total_paid": float(payload.get("total", 0.0)),
                "vat_rate": float(payload.get("Vat", 17.0)),
                "total_vat_paid": float(payload.get("totalVat", 0.0)),
                "payment_method": payload.get("payments", [{}])[0].get("name", "").strip() or "אשראי",
                "items": []
            }

            for item in payload.get("items", []):
                weight = item.get("weight")
                quantity = float(weight / 1000.0) if weight else float(item.get("quantity", 1.0))
                unit_price = float(item.get("price", 0.0))
                final_price = float(item.get("total", quantity * unit_price))
                expected_total = round(quantity * unit_price, 2)
                
                deal_description = ""
                add_info = item.get("additionalInfo", [])
                if isinstance(add_info, list) and len(add_info) > 0:
                    deal_description = str(add_info[0].get("key", "")).strip()

                has_deal = False
                discount_amount = 0.0
                if deal_description or final_price < expected_total:
                    has_deal = True
                    discount_amount = max(0.0, round(expected_total - final_price, 2))
                    if not deal_description:
                        deal_description = "מבצע רשת"

                unified_receipt["items"].append({
                    "description": item.get("name", "פריט").strip(),
                    "barcode": str(item.get("code")) if item.get("code") else None,
                    "is_by_weight": True if weight else False,
                    "quantity_or_weight": quantity,
                    "unit_price": unit_price,
                    "original_total_price": expected_total,
                    "is_part_of_deal": has_deal,
                    "deal_text": deal_description or None,
                    "discount_amount": discount_amount,
                    "final_price": final_price,
                    "category_path": item.get("category", ["כללי"])
                })

            return unified_receipt
        except Exception as ex:
            logger.error(f"Failed parsing inner metrics via Pairzon schema definition matrix: {ex}")
            raise ex