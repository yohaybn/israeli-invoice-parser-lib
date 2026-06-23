from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseReceiptParser(ABC):
    def __init__(self, store_name: str) -> None:
        self.store_name: str = store_name

    @abstractmethod
    def parse(self, source_data: str) -> Dict[str, Any]:
        pass

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