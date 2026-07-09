import logging
import re
import urllib
from urllib.parse import urlparse, parse_qs
from typing import Any, Dict, List, Optional
import requests
from bs4 import BeautifulSoup
from .base_parser import BaseReceiptParser  # Adjust import path based on your lib layout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PayperParser")
class PayperParser(BaseReceiptParser):


    def __init__(self) -> None:
        
        super().__init__(store_name="Payper Provider")

    def get_pdf_receipt_bytes(self, url: str) -> bytes:
        parsed_url = urllib.parse.urlparse(url.strip())
        queries = urllib.parse.parse_qs(parsed_url.query)
        path_string = urllib.parse.urlparse(url).path
        
        doc_id = queries.get("ak", [None])[0]
        pin_id = path_string.split('/')[-1]
                        
        pdf_url=f"https://app.payper.co.il/public/invoice_gateway/{pin_id}?ak={doc_id}"
        pdf_bytes=urllib.request.urlopen(pdf_url)
        return pdf_bytes.read()
    def parse(self, url: str) -> Dict[str, Any]:
        # 1. Download the HTML content
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Ensure correct encoding (frequently UTF-8 for Payper)
        response.encoding = 'utf-8'
        html_content = response.text
        
        # 2. Initialize BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        parsed_url = urlparse(url.strip())
        queries = parse_qs(parsed_url.query)
                
        doc_id = queries.get("ak", [None])[0]
        # 3. Extract Metadata & Core info
        store_name = self._safe_extract_text(soup.find('td', style=lambda x: x and 'width: 30%' in x).find('span', class_='f-bold'))
        
        # Get legal company ID (עוסק מורשה)
        legal_id_text = self._safe_extract_text(soup.find('td', style=lambda x: x and 'width: 30%' in x))
        company_legal_id = self._regex_search(r'עוסק מורשה\s*(\d+)', legal_id_text)
        
        # Get Receipt ID (from the main header "חשבונית מס קבלה 24")
        header_text = self._safe_extract_text(soup.find('div', class_='main-header'))
        receipt_id = self._regex_search(r'חשבונית מס קבלה\s*(\d+)', header_text) or self._regex_search(r'\d+', header_text)

        # Customer Info
        customer_td = soup.find('td', class_='honor-of')
        customer_text = self._safe_extract_text(customer_td)
        customer_name = self._regex_search(r'לכבוד:\s*\n?\s*([^\n]+)', customer_text)

        # Date
        date_td = soup.find('td', class_='invoice-date')
        date = self._safe_extract_text(date_td)
        
        # PDF / Download Document Link
        download_btn = soup.find('a', href=lambda x: x and '/public/invoice_gateway/' in x)
        pdf_url = f"https://app.payper.co.il{download_btn['href']}" if download_btn else url

        # 4. Extract Totals
        totals_section = soup.find('tbody', class_='totals')
        total_paid = 0.0
        vat_rate = 0.0
        total_vat_paid = 0.0
        
        if totals_section:
            for row in totals_section.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = self._safe_extract_text(cells[-2])
                    val_str = self._clean_price(self._safe_extract_text(cells[-1]))
                    
                    if "לתשלום" in label:
                        total_paid = float(val_str) if val_str else 0.0
                    elif "מע\"מ" in label:
                        total_vat_paid = float(val_str) if val_str else 0.0
                        vat_pct = self._regex_search(r'(\d+)%', label)
                        if vat_pct:
                            vat_rate = float(vat_pct)

        # 5. Payment Methods
        payment_method = None
        receipt_lines = soup.find_all('tr', id=lambda x: x and x.startswith('receipt_line_'))
        if receipt_lines:
            # Assuming the first payment medium listed
            payment_method_tds = receipt_lines[0].find_all('td')
            if payment_method_tds:
                payment_method = self._safe_extract_text(payment_method_tds[0])

        # 6. Parse Items Table
        items: List[Dict[str, Any]] = []
        # Find rows that represent item lines
        item_rows = soup.find_all('tr', id=lambda x: x and x.startswith('invoice_line_'))
        
        for row in item_rows:
            cells = row.find_all('td')
            if len(cells) >= 4:
                description = self._safe_extract_text(cells[0])
                quantity = float(self._clean_price(self._safe_extract_text(cells[1])) or 1.0)
                unit_price = float(self._clean_price(self._safe_extract_text(cells[2])) or 0.0)
                final_price = float(self._clean_price(self._safe_extract_text(cells[3])) or 0.0)
                
                items.append({
                    "description": description,
                    "barcode": None,
                    "is_by_weight": False,
                    "quantity_or_weight": quantity,
                    "unit_price": unit_price,
                    "original_total_price": final_price,
                    "is_part_of_deal": False,
                    "deal_text": None,
                    "discount_amount": 0.0,
                    "final_price": final_price,
                    "category_path": []
                })

        # 7. Map to JSON format
        return {
            "store_name": store_name,
            "pdf_url": pdf_url,
            "company_legal_id": company_legal_id,
            "branch_name": None,
            "store_address": None,
            "store_phone": None,
            "customer_name": customer_name,
            "date": date,
            "time": None, # The document provided only had a date
            "receipt_id": doc_id,
            "total_paid": total_paid,
            "vat_rate": vat_rate,
            "total_vat_paid": total_vat_paid,
            "payment_method": payment_method,
            "items": items
        }

    def _safe_extract_text(self, element) -> str:
        if element:
            return " ".join(element.get_text().split())
        return ""

    def _clean_price(self, text: str) -> str:
        # Removes currency signs and normalizes number strings
        cleaned = text.replace('₪', '').replace(',', '').strip()
        return cleaned

    def _regex_search(self, pattern: str, text: str) -> Optional[str]:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None