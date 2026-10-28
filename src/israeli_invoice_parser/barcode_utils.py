"""Generic barcode normalization for receipt items.

Receipts print item codes in many spellings: with or without leading zeros, UPC-A (12) or EAN-13, EAN-8, a chain's
short internal code ("41445"), or an in-store scale label that starts with 2 and carries the price or weight inside.
`describe_barcode()` turns one printed code into comparable, typed fields. It never guesses a product and never
looks anything up; matching against a price database stays with the caller.

Fields added to every item (all parsers, see BaseReceiptParser):
    barcode_normalized         digits only, leading zeros stripped ("0072900000414" -> "72900000414"); None if no digits
    barcode_kind               "gtin13" | "gtin8" | "upc12" | "gtin14" | "weighed" | "internal" | None
    barcode_gtin13             the 13-digit form of a real GTIN (UPC-A and EAN-8 zero-padded); None otherwise
    barcode_check_digit_valid  GS1 check digit is right (False for short/internal codes); None if no barcode
    weighed_item_code          for "weighed": the item (PLU) part, leading zeros stripped; else None
    weighed_embedded_value     for "weighed": the 5 digits before the check digit, as printed; else None
    weighed_embedded_kind      for "weighed": "price" (agorot) | "weight" (grams) | None when the line cannot tell
"""
from typing import Any, Dict, Optional

KINDS = ("gtin13", "gtin8", "upc12", "gtin14", "weighed", "internal")


def gs1_check_digit(body: str) -> str:
    """GS1 check digit for a body of any length (EAN-8: 7 digits, UPC-A: 11, EAN-13: 12, GTIN-14: 13)."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return str((10 - total % 10) % 10)


def has_valid_check_digit(code: str) -> bool:
    return len(code) >= 8 and code.isdigit() and gs1_check_digit(code[:-1]) == code[-1]


def _digits(raw: Any) -> str:
    return "".join(ch for ch in str(raw if raw is not None else "") if ch.isdigit())


def classify(raw: Any) -> Optional[str]:
    """The barcode kind of a printed code (see KINDS), or None when it has no digits."""
    code = _digits(raw)
    if not code:
        return None
    stripped = code.lstrip("0") or "0"
    if len(code) == 13 and code[0] == "2" and has_valid_check_digit(code):
        return "weighed"            # GS1 prefixes 20-29: in-store numbering, scale labels with price/weight inside
    for width, kind in ((8, "gtin8"), (12, "upc12"), (13, "gtin13"), (14, "gtin14")):
        if len(code) == width and has_valid_check_digit(code):
            if kind == "gtin14" and code[0] == "0":
                return classify(code[1:])
            if kind == "gtin13" and code[0] == "0" and has_valid_check_digit(code[1:]):
                return "upc12"      # an UPC-A written as EAN-13
            return kind
    if len(stripped) in (8, 12, 13) and stripped != code:
        return classify(stripped)   # extra leading zeros
    return "internal"


def _embedded_kind(value: str, item: Dict[str, Any]) -> Optional[str]:
    """Price or weight? Compare the embedded number with the line's own amounts (1 agora / 5 g tolerance)."""
    v = int(value)
    for key in ("final_price", "original_total_price"):
        price = item.get(key)
        if isinstance(price, (int, float)) and price > 0 and abs(v - round(price * 100)) <= 1:
            return "price"
    qty = item.get("quantity_or_weight")
    if item.get("is_by_weight") and isinstance(qty, (int, float)) and qty > 0 and abs(v - round(qty * 1000)) <= 5:
        return "weight"
    return None


def describe_barcode(raw: Any, item: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Typed, comparable fields for one printed code. `item` (the unified item dict) lets a scale label say whether
    its embedded number is the price or the weight."""
    code = _digits(raw)
    kind = classify(code)
    out: Dict[str, Any] = {
        "barcode_normalized": (code.lstrip("0") or "0") if code else None,
        "barcode_kind": kind,
        "barcode_gtin13": None,
        "barcode_check_digit_valid": has_valid_check_digit(code) if code else None,
        "weighed_item_code": None,
        "weighed_embedded_value": None,
        "weighed_embedded_kind": None,
    }
    if kind in ("gtin13", "gtin8", "upc12"):
        out["barcode_gtin13"] = out["barcode_normalized"].zfill(13)
    elif kind == "gtin14" and code[0] != "0":
        out["barcode_gtin13"] = None           # a GTIN-14 with a packaging indicator has no 13-digit form
    if kind == "weighed":
        out["weighed_item_code"] = code[2:7].lstrip("0") or "0"
        out["weighed_embedded_value"] = code[7:12]
        out["weighed_embedded_kind"] = _embedded_kind(code[7:12], item or {})
    return out


def add_barcode_fields(receipt: Any) -> Any:
    """Add describe_barcode()'s fields to every item of a unified receipt dict (in place; returns it).
    Only new keys are added; existing keys are never changed."""
    if not isinstance(receipt, dict):
        return receipt
    for item in receipt.get("items") or []:
        if isinstance(item, dict):
            for key, value in describe_barcode(item.get("barcode"), item).items():
                item.setdefault(key, value)
    return receipt
