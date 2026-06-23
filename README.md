# israel-invoice-parser

A unified, highly accurate Python parsing library for Israeli digital receipts, grocery bills, and commercial retail invoices. This library standardizes fragmented vendor payloads (including direct APIs, raw HTML, and complex Nuxt transport matrices) into a single, clean, structured Python dictionary.

## Supported Retailers & Providers

The library supports major Israeli storefronts directly or via central receipt infrastructure aggregators:

*   **Rami Levy (רמי לוי)** — Native support for standard digital bills and microservice data streams.
*   **Pairzon Engine (פיירזון)** — Dynamic resolution for short-link token routers and partner store layouts (e.g., **Yohananof (יוחננוף)**, **Osher Ad (אושר עד)**, **Max Stock (מקס סטוק)**, etc.).
*   **Weezmo / Wee.ai Infrastructure** — Multi-brand validation supporting high-street retail setups, fashion entities (**TopTen**, **Tamnun**), and grocery gateways.

> ⚠️ **Current Limitations:** Automated extraction for **Shufersal (שופרסל)** invoices is currently broken or unmapped due to recent structure changes. We are actively looking for contributors or sample inputs to restore this!

---

## Installation

Install the package via `pip`:

```bash
pip install israel-invoice-parser
```

---

## Quick Start & Usage Examples

Every parser inherits from a common interface (`BaseReceiptParser`) and returns a standardized data model, making it simple to process invoices interchangeably.

### 1. Parsing a Rami Levy URL
```python
from invoice_parser import RamiLevyParser

# Initialize the dedicated parser
parser = RamiLevyParser()

# Pass a live receipt or invoice URL directly
url = "https://api-digi.rami-levy.co.il/api/v1/receipts/example-token-12345"
receipt = parser.parse(url)

# Access standardized fields uniformly
print(f"Store: {receipt['store_name']}")
print(f"Total Paid: ₪{receipt['total_paid']}")
print(f"Date: {receipt['date']} at {receipt['time']}")

for item in receipt['items']:
    print(f" - {item['description']}: ₪{item['final_price']} (Qty: {item['quantity_or_weight']})")
```

### 2. Parsing a Pairzon Provider Short-Link (e.g., Yohananof / Osher Ad)
```python
from invoice_parser import PairzonParser

parser = PairzonParser()

# Works with central Pairzon tracking tokens or short links
pairzon_url = "https://pzn.io/r/v123abcd" 
receipt = parser.parse(pairzon_url)

# The parser dynamically extracts real corporate metadata to identify the sub-brand
print(f"Identified Brand: {receipt['store_name']}")  # e.g., 'יוחננוף' or 'אושר עד'
print(f"Legal Business ID: {receipt['company_legal_id']}")
```

### 3. Standardized Output Format Matrix
Regardless of which vendor parser is called, the output dictionary always complies with the following layout structure:

```python
{
    "store_name": "רמי לוי",
    "company_legal_id": "513770669",
    "branch_name": "סניף תל אביב",
    "store_address": "דרך מנחם בגין 123",
    "store_phone": "03-1234567",
    "customer_name": "ישראל ישראלי",
    "date": "23/06/2026",
    "time": "14:30:00",
    "receipt_id": "987654321",
    "total_paid": 245.50,
    "vat_rate": 17.0,
    "total_vat_paid": 35.67,
    "payment_method": "אשראי",
    "items": [
        {
            "description": "חלב תנובה 3%",
            "barcode": "7290000042431",
            "is_by_weight": False,
            "quantity_or_weight": 2.0,
            "unit_price": 6.50,
            "original_total_price": 13.00,
            "is_part_of_deal": True,
            "deal_text": "2 ב-₪11",
            "discount_amount": 2.00,
            "final_price": 11.00,
            "category_path": ["סופרמרקט"]
        }
    ]
}
```

---

## 🤝 Contributing & Helping Out

Parsing real-world digital invoices is a game of cat-and-mouse as retailers update their internal schemas. We need your help to make this library resilient!

### Have an Unsupported Receipt / Found a Bug?
If you run into an invoice that fails to parse (such as **Shufersal** or a newly formatted receipt):
1. [Open a New Issue](https://github.com/yourusername/israeli-invoice-parser/issues) on GitHub.
2. Provide a **link to the invoice** or the raw anonymized data payload.
3. We will inspect the network footprint and write/update a parser for it!

### Want to Add a New Parser?
We warmly welcome pull requests! To contribute a new parser:
1. Subclass `BaseReceiptParser` from `base_parser.py`.
2. Implement the `.parse(self, source_data: str) -> Dict[str, Any]` method.
3. Map the data cleanly into our uniform dictionary format.
4. Submit a PR!

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
