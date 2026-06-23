import json
import logging
import os
import re
import urllib.request
import urllib.error
from typing import Dict, Any
from bs4 import BeautifulSoup
from .base_parser import BaseReceiptParser, NuxtDataHydrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RamiLevyParser")

class RamiLevyParser(BaseReceiptParser):
    def __init__(self) -> None:
        super().__init__(store_name="Rami Levy")

    def parse(self, source_data: str) -> Dict[str, Any]:
        html_content = ""

        if source_data.startswith("http://") or source_data.startswith("https://"):
            try:
                # Clean and identify short links vs direct data resources
                target_url = source_data.strip()
                logger.info(f"Downloading live Rami Levy content context: {target_url}")
                
                # Emulate a complete browser identity to step through security filters
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
                
                req = urllib.request.Request(target_url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response:
                    html_content = response.read().decode('utf-8')
                    
                # Save data backup trace locally for evaluation
                os.makedirs("temp", exist_ok=True)
                with open("temp/rami_levy_raw_page.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                    
            except urllib.error.HTTPError as http_err:
                logger.error(f"Rami Levy gateway connection dropped (HTTP {http_err.code})")
                raise ValueError(f"נכשל חיבור לשרת רמי לוי. קוד שגיאה: {http_err.code}")
            except Exception as e:
                logger.error(f"Failed downloading remote Rami Levy page context: {e}")
                raise e
        else:
            html_content = source_data

        try:
            raw_json_text = ""
            
            # 1. Standard HTML Extraction Flow
            if "<script" in html_content or "<body" in html_content:
                soup = BeautifulSoup(html_content, "html.parser")
                nuxt_script = soup.find("script", id="__NUXT_DATA__")
                if not nuxt_script:
                    nuxt_script = soup.find("script", string=re.compile(r'__NUXT_DATA__'))
                
                if nuxt_script:
                    raw_json_text = nuxt_script.string if nuxt_script.string else nuxt_script.text
            
            # 2. API Fallback Flow (If Nuxt text blocks are missing or encoded)
            if not raw_json_text.strip():
                logger.info("Script extraction returned empty text. Attempting API transformation route...")
                # Extract the token directly out of the URL path (e.g. /0fFlup4Bp5Iw_ikNn9ZU)
                url_path = urlparse(source_data).path if source_data.startswith("http") else ""
                token_match = re.search(r'/([^/]+)$', url_path)
                
                if token_match:
                    token = token_match.group(1)
                    # Query Rami Levy's microservice data endpoint directly 
                    api_fallback_url = f"https://api-digi.rami-levy.co.il/api/v1/receipts/{token}"
                    logger.info(f"Querying production backup data endpoint: {api_fallback_url}")
                    
                    api_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                        'Accept': 'application/json'
                    }
                    fallback_req = urllib.request.Request(api_fallback_url, headers=api_headers)
                    with urllib.request.urlopen(fallback_req, timeout=15) as fallback_res:
                        raw_json_text = fallback_res.read().decode('utf-8')
                else:
                    raise ValueError("Could not extract document tracking tokens from provided link layout.")

            if not raw_json_text.strip():
                raise ValueError("Rami Levy parsing sequence generated an empty payload text string.")

            raw_payload = json.loads(raw_json_text.strip())

            # Backup uncompressed JSON objects locally
            with open("temp/rami_levy_raw.json", "w", encoding="utf-8") as f:
                json.dump(raw_payload, f, ensure_ascii=False, indent=2)

            # Initialize hydration pipeline
            # If the payload is from the backup direct API, it will already be unflattened.
            # If it's standard Nuxt transport text, use index 5 to expand the root data trees.
            if isinstance(raw_payload, list):
                hydrator = NuxtDataHydrator(raw_payload)
                # Search across primary structural indices for receipt context arrays
                receipt_core = None
                for base_index in (5, 4, 3, 2, 1):
                    try:
                        node = hydrator.hydrate_node(base_index)
                        if isinstance(node, dict) and ("items" in node or "branch" in node):
                            receipt_core = node
                            break
                        elif isinstance(node, dict) and "data" in node:
                            inner_data = node["data"]
                            if isinstance(inner_data, dict):
                                # Loop keys to check for hidden instances
                                for k, v in inner_data.items():
                                    if isinstance(v, dict) and "items" in v:
                                        receipt_core = v
                                        break
                    except Exception:
                        continue
                if not receipt_core:
                    raise ValueError("Failed to locate receipt parameters inside the Nuxt transport grid.")
            else:
                # Payload is already standard dictionary data from API backup stream
                receipt_core = raw_payload.get("data", raw_payload)

            branch_info = receipt_core.get("branch", {}) or {}
            company_info = receipt_core.get("company", {}) or {}
            payment_core = receipt_core.get("payments", {}) or {}
            
            methods_list = payment_core.get("methods", [])
            primary_method = methods_list[0] if isinstance(methods_list, list) and len(methods_list) > 0 else {}

            created_at = receipt_core.get("created_at", "2026-01-01T00:00:00.000Z")
            date_part, time_part = created_at.split("T") if "T" in created_at else (created_at, "00:00:00")
            if "-" in date_part:
                parts = date_part.split("-")
                formatted_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
            else:
                formatted_date = date_part

            unified_receipt: Dict[str, Any] = {
                "store_name": self.store_name,
                "company_legal_id": str(company_info.get("tax_id", receipt_core.get("business_id", "513770669"))),
                "branch_name": str(branch_info.get("name", "רמי לוי סניף")).strip(),
                "store_address": str(company_info.get("address", "")).strip(),
                "store_phone": str(company_info.get("customer_service", {}).get("branch_phone", "")).strip(),
                "customer_name": str(receipt_core.get("customer", {}).get("name", "")).strip() or None,
                "date": formatted_date,
                "time": time_part[:8],
                "receipt_id": str(receipt_core.get("transaction_id", receipt_core.get("id", ""))),
                "total_paid": float(payment_core.get("total", receipt_core.get("total", 0.0))),
                "vat_rate": float(receipt_core.get("vat_rate", 18.0)),
                "total_vat_paid": float(payment_core.get("total_vat", 0.0)),
                "payment_method": str(primary_method.get("name", "אשראי")).strip(),
                "items": []
            }

            for item in receipt_core.get("items", []):
                if not isinstance(item, dict):
                    continue

                weight_val = item.get("weight")
                quantity = float(weight_val / 1000.0) if weight_val else float(item.get("quantity", 1.0))
                unit_price = float(item.get("price", 0.0))
                
                expected_total = round(quantity * unit_price, 2)
                
                discount_amount = 0.0
                deal_description = ""
                add_info = item.get("additional_info", [])
                if isinstance(add_info, list):
                    for info_node in add_info:
                        if isinstance(info_node, dict) and "value" in info_node:
                            val_str = str(info_node.get("value", "0"))
                            if "-" in val_str:
                                try:
                                    discount_amount = abs(float(val_str))
                                    deal_description = str(info_node.get("key", "")).strip()
                                except ValueError:
                                    pass

                final_price = round(expected_total - discount_amount, 2)
                # Verify cross-referenced pricing boundaries
                if final_price <= 0 and item.get("total"):
                    final_price = float(item.get("total"))

                has_deal = True if (discount_amount > 0 or deal_description) else False

                unified_receipt["items"].append({
                    "description": str(item.get("name", "פריט")).strip(),
                    "barcode": str(item.get("code")) if item.get("code") else None,
                    "is_by_weight": True if weight_val else False,
                    "quantity_or_weight": quantity,
                    "unit_price": unit_price,
                    "original_total_price": expected_total,
                    "is_part_of_deal": has_deal,
                    "deal_text": deal_description or None,
                    "discount_amount": discount_amount,
                    "final_price": final_price,
                    "category_path": ["סופרמרקט"]
                })

            return unified_receipt
        except Exception as ex:
            logger.error(f"Error expanding serialized Rami Levy tables: {ex}")
            raise ex