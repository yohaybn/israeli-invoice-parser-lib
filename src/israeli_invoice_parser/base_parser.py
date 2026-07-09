from abc import ABC, abstractmethod
from typing import Dict, Any, List
import urllib.request
import logging

logger = logging.getLogger(__name__)
class BaseReceiptParser(ABC):
    def __init__(self, store_name: str) -> None:
        self.store_name: str = store_name

    @abstractmethod
    def parse(self, url: str) -> Dict[str, Any]:
        pass

    def get_pdf_receipt_bytes(self, url: str) -> bytes:
        invoice=self.parse(url)
        logger.info(f"Downloading {self.store_name} PDF receipt from: {invoice['pdf_url']}")
        pdf_bytes=urllib.request.urlopen(invoice["pdf_url"])
        return pdf_bytes.read()
    def get_parser_name(self) -> str:
        return self.__class__.__name__
class NuxtDataHydrator:
    """
    Decompresses multi-type transport data matrices from Nuxt 3 back 
    into standard dictionaries, cleanly handling cross-referenced table indices.
    """
    def __init__(self, data_list: List[Any]) -> None:
        self.raw_pool: List[Any] = data_list
        self.visited = set()

    def hydrate_node(self, node: Any) -> Any:
        if isinstance(node, int) and 0 <= node < len(self.raw_pool):
            if node in self.visited:
                return f"<CircularRef: Index {node}>"
            
            self.visited.add(node)
            resolved = self.raw_pool[node]
            result = self._transform(resolved)
            self.visited.remove(node)
            return result
        return self._transform(node)

    def _transform(self, val: Any) -> Any:
        if isinstance(val, dict):
            return {k: self.hydrate_node(v) for k, v in val.items()}
        elif isinstance(val, list):
            if val and val[0] in ("ShallowReactive", "Reactive", "ShallowRef", "Ref"):
                return self.hydrate_node(val[1])
            return [self.hydrate_node(item) for item in val]
        return val