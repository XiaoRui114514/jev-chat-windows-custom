"""Structured messages and explicit confidence, independent of Qt/capture."""
from dataclasses import asdict, dataclass, field
from hashlib import sha256
import math

TYPES = {"text", "image", "emoji", "sticker", "gif", "video", "video_channel",
         "article", "link", "file", "voice", "system", "unknown"}

def unit(value, default=0.0):
    try:
        n = float(value)
        return min(1.0, max(0.0, n)) if math.isfinite(n) else default
    except (ValueError, TypeError):
        return default

@dataclass
class Message:
    sender: str = "unknown"
    text: str = ""
    type: str = "unknown"
    name: str | None = None
    timestamp: str | None = None
    bounds: tuple[int, int, int, int] | None = None
    ocr_confidence: float = 0.0
    sender_confidence: float = 0.0
    type_confidence: float = 0.0
    metadata: dict = field(default_factory=dict)
    id: str = ""

    @property
    def overall_confidence(self):
        values = [unit(self.sender_confidence), unit(self.type_confidence)]
        if self.text:
            values.append(unit(self.ocr_confidence))
        return min(values)

    def to_dict(self):
        out = asdict(self)
        out["from"] = out.pop("sender")
        out["overall_confidence"] = self.overall_confidence
        return out

    def identify(self, fingerprint=""):
        value = f"{self.sender}|{self.name or ''}|{self.type}|{self.text}|{fingerprint}"
        self.id = sha256(value.encode()).hexdigest()[:24]
        return self

