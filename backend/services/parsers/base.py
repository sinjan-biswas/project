from abc import ABC, abstractmethod

class DocumentParser(ABC):
    document_type: str = "unknown"

    @abstractmethod
    def parse(self, lines: list[dict], full_text: str) -> dict:
        """Return {'document_type': str, 'fields': dict, 'confidence': float}"""