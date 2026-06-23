# israeli-invoice-parser

A unified, highly accurate Python parsing library for Israeli digital receipts, grocery bills, and commercial retail invoices. This library standardizes fragmented vendor payloads (including direct APIs, raw HTML, and complex Nuxt transport matrices) into a single, clean, structured Python dictionary.

## Supported Retailers and Providers

The library supports major Israeli storefronts directly or via central receipt infrastructure aggregators:

*   **Rami Levy (רמי לוי)** — Native support for standard digital bills and microservice data streams.
*   **Weezmo / Wee.ai Infrastructure** — Multi-brand validation supporting grocery gateways like **Yohananof (יוחננוף)**, high-street retail setups, and fashion entities (**TopTen**, **Tamnun**).
*   **Pairzon Engine (פיירזון)** — Dynamic resolution for short-link token routers and partner store layouts (e.g., **Osher Ad (אושר עד)**, **Max Stock (מקס סטוק)**, etc.).

> **Current Limitations:** Automated extraction for **Shufersal (שופרסל)** invoices is currently blocked. The endpoint uses robust bot-protection / WAF rules that reject standard programmatic requests. We are actively trying to figure out how to bypass or properly emulate browser signatures to restore this functionality. Contributions or ideas on this technical issue are highly appreciated!

---

## Installation

Install the package via `pip`:

```bash
pip install israel-invoice-parser

```

---

## Quick Start and Usage Examples

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

### 2. Parsing a Weezmo / Wee.ai Provider Short-Link (e.g., Yohananof)

```python
from invoice_parser import WeezmoParser

parser = WeezmoParser()

# Works with central wee.ai tracking tokens or short links
weezmo_url = "https://wee.ai/r/v123abcd" 
receipt = parser.parse(weezmo_url)

# The parser dynamically extracts real corporate metadata to identify the sub-brand
print(f"Identified Brand: {receipt['store_name']}")  # e.g., 'יוחננוף'
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

## Contributing and Helping Out

Parsing real-world digital invoices is a game of cat-and-mouse as retailers update their internal schemas. We need your help to make this library resilient!

### Have an Unsupported Receipt / Found a Bug?

If you run into an invoice that fails to parse (such as **Shufersal** or a newly formatted receipt Layout):

1. Open a New Issue on the [israeli-invoice-parser-lib Bug Tracker](https://github.com/yohaybn/israeli-invoice-parser-lib/issues).
2. **Crucial:** Provide a **real, live link to the invoice**. Without a working URL, it is impossible to inspect the underlying network payload structure, test backend responses, or map out the necessary payload parameters.
3. If you have suggestions or workarounds for bypassing Shufersal's anti-bot restrictions, please detail them inside the dedicated discussion issues!

### Want to Add a New Parser?

We warmly welcome pull requests! To contribute a new parser:

1. Subclass `BaseReceiptParser` from `base_parser.py`.
2. Implement the `.parse(self, source_data: str) -> Dict[str, Any]` method.
3. Map the data cleanly into our uniform dictionary format.
4. Submit your PR directly to the [GitHub Repository](https://github.com/yohaybn/israeli-invoice-parser-lib/).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
