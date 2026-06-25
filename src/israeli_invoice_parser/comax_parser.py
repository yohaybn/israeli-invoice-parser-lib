import logging
import re
import urllib.error
import urllib.request
from typing import Any, Dict
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from .base_parser import BaseReceiptParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ComaxParser")


class ComaxParser(BaseReceiptParser):

    def __init__(self) -> None:
        super().__init__(store_name="Comax POS Provider")
        # Matches structural item lines: Barcode, Item Name, Base Price
        self.item_pattern = re.compile(r"^(\d{7,14})\s+(.*?)\s+(-?\d+\.\d+)\s*$")
        # Matches inline operational quantities: Price X Qty Total
        self.qty_pattern = re.compile(
            r"(-?\d+\.\d+)\s*[xX𝘅✖]\s*(\d+(?:\.\d+)?)\s+(-?\d+\.\d+)"
        )

    def _sanitize_text(self, text: str) -> str:
        if not text:
            return ""
        # Force conversion of all non-breaking spacer tokens down to single character spaces
        text = text.replace("&nbsp", " ").replace("\xa0", " ")
        return " ".join(text.split())

    def parse(self, source_data: str) -> Dict[str, Any]:
        raw_html: str = ""

        # Step 1: Handle network stream acquisition if input acts as a reference tracking link
        if source_data.startswith("http://") or source_data.startswith(
            "https://"
        ):
            try:
                base_url = source_data.strip()
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Connection": "close",
                }

                # Setup implicit 302/301 follow handler block
                class FollowRedirectHandler(urllib.request.HTTPRedirectHandler):

                    def http_error_302(self, req, fp, code, msg, headers):
                        return super().http_error_302(
                            req, fp, code, msg, headers
                        )

                opener = urllib.request.build_opener(FollowRedirectHandler())
                req = urllib.request.Request(base_url, headers=headers)

                logger.info(
                    f"Fetching remote Comax data instance from: {base_url}"
                )
                with opener.open(req, timeout=10) as response:
                    raw_html = response.read().decode("utf-8")

            except urllib.error.HTTPError as http_err:
                logger.error(
                    f"Comax network service failure endpoint: {http_err.code}"
                )
                raise ValueError(
                    f"שגיאת תקשורת מול שרת קומקס: קוד {http_err.code}"
                )
            except urllib.error.URLError as url_err:
                logger.error(f"Comax communication limit timeout: {url_err.reason}")
                raise ValueError(
                    "חיבור הרשת לשרת קומקס נותק או הגיע למגבלת זמן (Timeout)."
                )
            except Exception as e:
                logger.error(
                    f"Critical initialization failure parsing Comax sequence: {e}"
                )
                raise e
        else:
            raw_html = source_data

        # Step 2: Extract text nodes using beautifulsoup
        soup = BeautifulSoup(raw_html, "html.parser")
        divs = [
            self._sanitize_text(div.get_text())
            for div in soup.find_all("div")
            if div.get_text()
        ]

        if not divs:
            raise ValueError(
                "Could not extract valid structural payload bounds from the provided HTML data stream."
            )

        # Build structural mapping response template
        unified_receipt: Dict[str, Any] = {
            "store_name": self.store_name,
            "pdf_url": None,
            "company_legal_id": None,
            "branch_name": None,
            "store_address": None,
            "store_phone": None,
            "customer_name": None,
            "date": None,
            "time": None,
            "receipt_id": None,
            "total_paid": 0.0,
            "vat_rate": 0.0,  # Comax structural defaults for specific areas or explicitly calculated from totals
            "total_vat_paid": 0.0,
            "payment_method": "אשראי",
            "items": [],
        }

        # Resolve printable/downloadable copy source mapping links
        pdf_link = soup.find("a", href=True)
        if pdf_link:
            unified_receipt["pdf_url"] = pdf_link["href"]

        # Parse structural header and summary components
        for i, text in enumerate(divs):
            if "ח.פ" in text:
                # Comax header index pattern shifts
                unified_receipt["store_name"] = divs[i - 3] if i >= 3 else None
                unified_receipt["branch_name"] = divs[i - 2] if i >= 2 else None
                unified_receipt["store_address"] = (
                    divs[i - 2] if i >= 2 else None
                )
                unified_receipt["company_legal_id"] = re.sub(r"\D", "", text)
                self.store_name = unified_receipt["store_name"]

            elif "חשבונית מס/קבלה" in text:
                unified_receipt["receipt_id"] = re.sub(r"\D", "", text)

            elif "תאריך קניה" in text:
                date_match = re.search(
                    r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})", text
                )
                if date_match:
                    unified_receipt["date"] = date_match.group(1)
                    unified_receipt["time"] = f"{date_match.group(2)}:00"

            elif "לכבוד:" in text:
                unified_receipt["customer_name"] = (
                    text.replace("לכבוד:", "").strip()
                )

            elif "טלפון:" in text:
                phone_match = re.search(r"טלפון:\s*(\d+)", text)
                if phone_match:
                    unified_receipt["store_phone"] = phone_match.group(1)

            elif "לתשלום" in text:
                total_match = re.search(r"לתשלום\s+(-?\d+\.\d+)", text)
                if total_match:
                    unified_receipt["total_paid"] = float(total_match.group(1))

        # Step 3: Parse and loop structured line items
        i = 0
        while i < len(divs):
            text = divs[i]

            item_match = self.item_pattern.match(text)
            if item_match:
                barcode, description, base_price_str = item_match.groups()
                base_price = float(base_price_str)

                # Initialize normal transaction parameters
                quantity = 1.0
                unit_price = base_price
                final_price = base_price

                # Check ahead for matching calculation metadata details block (skipping inner tax status labels)
                peek_idx = i + 1
                while peek_idx < len(divs):
                    peek_text = divs[peek_idx]
                    if 'מע"מ' in peek_text:
                        peek_idx += 1
                        continue

                    qty_match = self.qty_pattern.match(peek_text)
                    if qty_match:
                        u_price, qty, t_price = qty_match.groups()
                        unit_price = float(u_price)
                        quantity = float(qty)
                        final_price = float(t_price)
                        i = peek_idx
                    break

                is_weight = not quantity.is_integer()
                expected_total = round(quantity * unit_price, 2)

                unified_receipt["items"].append(
                    {
                        "description": description.strip(),
                        "barcode": barcode,
                        "is_by_weight": is_weight,
                        "quantity_or_weight": quantity,
                        "unit_price": unit_price,
                        "original_total_price": expected_total,
                        "is_part_of_deal": False,
                        "deal_text": None,
                        "discount_amount": 0.0,
                        "final_price": final_price,
                        "category_path": ["סופרמרקט"],
                    }
                )

            # Extract distinct deal nodes and attach them to the preceding item safely
            elif text.startswith("*") and "מבצע" in text:
                deal_description = text.strip("* ")
                if i + 1 < len(divs):
                    next_text = divs[i + 1]
                    qty_match = self.qty_pattern.match(next_text)
                    if qty_match:
                        _, _, t_price = qty_match.groups()
                        discount_amount = abs(float(t_price))

                        if unified_receipt["items"]:
                            last_item = unified_receipt["items"][-1]
                            last_item["is_part_of_deal"] = True
                            last_item["deal_text"] = deal_description
                            last_item["discount_amount"] = discount_amount
                            last_item["final_price"] = round(
                                last_item["final_price"] - discount_amount, 2
                            )
                        i += 1

            i += 1

        return unified_receipt