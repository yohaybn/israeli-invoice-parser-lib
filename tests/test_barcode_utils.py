import io
import json
import urllib.request
from unittest import mock

import pytest

from israeli_invoice_parser import ComaxParser, WeezmoParser, classify, describe_barcode
from israeli_invoice_parser.barcode_utils import add_barcode_fields, gs1_check_digit


def scale_label(item, value, flag="0"):
    body = "2" + flag + item.zfill(5) + value.zfill(5)
    return body + gs1_check_digit(body)


# --- classify -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,kind", [
    ("7290000041445", "gtin13"),
    ("07290000041445", "gtin13"),     # GTIN-14 spelling of an EAN-13
    ("96385074", "gtin8"),
    ("036000291452", "upc12"),
    ("0036000291452", "upc12"),       # UPC-A written as EAN-13
    ("41445", "internal"),            # chain short code
    ("7290000041446", "internal"),    # bad check digit
    ("10614141000415", "gtin14"),
    ("", None),
    (None, None),
])
def test_classify(raw, kind):
    assert classify(raw) == kind


def test_scale_label_is_weighed():
    assert classify(scale_label("1234", "1590")) == "weighed"


# --- describe_barcode -----------------------------------------------------------------------------------------

def test_gtin13_fields():
    d = describe_barcode("07290000041445")
    assert d["barcode_normalized"] == "7290000041445"
    assert d["barcode_kind"] == "gtin13"
    assert d["barcode_gtin13"] == "7290000041445"
    assert d["barcode_check_digit_valid"] is True    # leading zeros never change a GS1 check digit
    assert d["weighed_item_code"] is None


def test_upc_and_ean8_padded_to_13():
    assert describe_barcode("036000291452")["barcode_gtin13"] == "0036000291452"
    assert describe_barcode("96385074")["barcode_gtin13"] == "0000096385074"


def test_internal_code_has_no_gtin13():
    d = describe_barcode("41445")
    assert d["barcode_kind"] == "internal"
    assert d["barcode_gtin13"] is None
    assert d["barcode_check_digit_valid"] is False
    assert d["barcode_normalized"] == "41445"


def test_scale_label_price_inside():
    code = scale_label("1234", "1590")
    d = describe_barcode(code, {"final_price": 15.90, "is_by_weight": True, "quantity_or_weight": 0.8})
    assert d["weighed_item_code"] == "1234"
    assert d["weighed_embedded_value"] == "01590"
    assert d["weighed_embedded_kind"] == "price"


def test_scale_label_weight_inside():
    code = scale_label("777", "850")
    d = describe_barcode(code, {"final_price": 21.20, "is_by_weight": True, "quantity_or_weight": 0.85})
    assert d["weighed_embedded_kind"] == "weight"


def test_scale_label_unknown_without_context():
    assert describe_barcode(scale_label("777", "850"))["weighed_embedded_kind"] is None


def test_none_barcode():
    d = describe_barcode(None)
    assert d["barcode_normalized"] is None and d["barcode_kind"] is None and d["barcode_check_digit_valid"] is None


def test_add_barcode_fields_only_adds_keys():
    r = {"items": [{"barcode": "41445", "is_by_weight": False, "barcode_kind": "kept"}]}
    add_barcode_fields(r)
    assert r["items"][0]["barcode_kind"] == "kept"           # an existing key is never overwritten
    assert r["items"][0]["barcode_normalized"] == "41445"
    assert add_barcode_fields(None) is None


# --- every parser's output carries the fields --------------------------------------------------------------------

COMAX_HTML = """<html><body>
<div>מכולת דוגמה</div><div>סניף</div><div>רחוב 1</div><div>ח.פ 000000000</div>
<div>תאריך קניה 20/10/2026 12:30</div>
<div>7290000041445 קוטג 5% 5.90</div>
<div>036000291452 מוצר מיובא 9.90</div>
<div>לתשלום 15.80</div>
</body></html>"""


def test_comax_items_get_barcode_fields():
    r = ComaxParser().parse(COMAX_HTML)
    kinds = [(i["barcode"], i["barcode_kind"], i["barcode_gtin13"]) for i in r["items"]]
    assert kinds == [("7290000041445", "gtin13", "7290000041445"), ("036000291452", "upc12", "0036000291452")]
    assert r["items"][0]["final_price"] == 5.90               # existing fields unchanged


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_weezmo_items_get_barcode_fields():
    payload = {"tBusiness": {"businessName": "יוחננוף"}, "tBranch": {"branchName": "סניף"},
               "createdDate": "2026-10-08T09:00:00Z", "total": 6.9,
               "items": [{"itemCode": "1022801", "name": "גבינה", "price": 59.9, "quantity": 0.35, "total": 20.97}]}
    body = json.dumps(payload).encode("utf-8")
    with mock.patch.object(urllib.request, "urlopen", lambda *a, **k: _Resp(body)):
        r = WeezmoParser().parse("https://receipts.weezmo.com/cms.html?q=abc")
    item = r["items"][0]
    assert item["barcode_kind"] == "internal" and item["barcode_normalized"] == "1022801"
