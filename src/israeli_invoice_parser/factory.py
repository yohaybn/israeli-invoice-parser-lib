import logging
from typing import Any, Dict, Optional, Type

# Use relative dot notation directly to sibling files
from .base_parser import BaseReceiptParser
from .comax_parser import ComaxParser
from .pairzon_parser import PairzonParser
from .rami_levy_parser import RamiLevyParser
from .weezmo_parser import WeezmoParser

logger = logging.getLogger("InvoiceParserFactory")


class ReceiptParserFactory:
    # A registry mapping substring signatures found in URLs to their respective Parser Classes
    _PROVIDER_REGISTRY: Dict[str, Type[BaseReceiptParser]] = {
        "pairzon.com": PairzonParser,
        "rami-levy.co.il": RamiLevyParser,
        "wee.ai": WeezmoParser,
        "weezmo.com": WeezmoParser,
        "comax.co.il": ComaxParser,
    }

    @classmethod
    def get_parser_for_url(cls, url: str) -> Optional[BaseReceiptParser]:
        """Inspects the URL string and returns an instantiated parser instance

        matching the known provider domain signature.
        """
        if not url or not isinstance(url, str):
            return None

        normalized_url = url.lower().strip()

        # Check for signature matches inside the provided string path
        for signature, parser_class in cls._PROVIDER_REGISTRY.items():
            if signature in normalized_url:
                logger.info(
                    f"Auto-detected signature '{signature}'. Routing to {parser_class.__name__}."
                )
                return parser_class()

        logger.warning(
            f"No structural provider signature matched for input path: {url}"
        )
        return None

    @classmethod
    def parse_automatically(cls, source_data: str) -> Optional[Dict[str, Any]]:
        """Automatically detects the host provider, fetches, and parses the receipt matrix.

        If it's a raw string payload instead of a URL, you can fallback to a default
        parser or return None.
        """
        source_data_clean = source_data.strip()

        if source_data_clean.startswith("http://") or source_data_clean.startswith("https://"):
            parser = cls.get_parser_for_url(source_data_clean)
            if parser:
                return parser.parse(source_data_clean)

        # Optional: Add raw payload fallback heuristics if source data is raw HTML or JSON text instead of a URL
        logger.error(
            "Auto-identification requires a valid URL stream signature string."
        )
        return None