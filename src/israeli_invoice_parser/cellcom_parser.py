import logging
import urllib
from urllib.parse import parse_qs
from typing import Any, Dict 
import requests
import base64
from .base_parser import BaseReceiptParser  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CellcomParser")
class CellcomParser(BaseReceiptParser):


    def __init__(self) -> None:
        
        super().__init__(store_name="Cellcom Provider")

    def get_pdf_receipt_bytes(self, url: str) -> bytes:
        #https://cellcom.co.il/selfcare/InvoicePageNew/?id=14112ED8-FD94-8B12-8518-B4E49A22DC00
        parsed_url = urllib.parse.urlparse(url.strip())
        
        queries = parse_qs(parsed_url.query)
        
        invoice_id = queries.get("id", [None])[0]
        pdf_api_url="https://digital-api.cellcom.co.il/api/Ibill/GetPdfLogAuth"
        payload={'invoiceId':invoice_id,'doAccessibilityLayer':0,'consolidationPdf': False}
        logger.info(url)
        logger.info(payload)
        res=requests.post(url=pdf_api_url,json=payload)
        logger.info(f"Status Code:{res.status_code} ")
        return base64.b64decode(res.json()["Body"]["pdfResponse"]["base64"])

    def parse(self, url: str) -> Dict[str, Any]:
        raise NotImplementedError("Not implemented yet")
    def get_parser_name(self) -> str:
        return "CellcomParser"