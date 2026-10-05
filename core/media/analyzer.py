import hashlib
import time
import numpy as np
from core.errors import JevError
from .cache import TTLCache
from .vision import OpenAIVision

GATES = {"video_channel": "video_channel", "article": "article", "link": "article",
         "image": "image", "sticker": "sticker", "gif": "sticker"}

def selected(message, options):
    return (message.get("from") == "her" and message.get("sender_confidence", 0) >= .75
            and options.get(GATES.get(message.get("type")), False) is True)

class MediaAnalyzer:
    def __init__(self, vision=None, cache=None, max_calls=3):
        self.vision = vision or OpenAIVision()
        self.cache = cache or TTLCache()
        self.max_calls = max_calls

    def enrich(self, messages, crops, options, config):
        started = time.perf_counter()
        stats = {"vision_ms": 0, "vision_calls": 0, "cache_hits": 0, "errors": []}
        out = []
        for original in messages:
            m = {**original, "metadata": dict(original.get("metadata") or {})}
            out.append(m)
            if not selected(m, options):
                continue
            packet = crops.get(m.get("id"))
            if packet is None:
                m["metadata"]["recognition_status"] = "没有可用的消息裁剪区域"
                continue
            if isinstance(packet, dict):
                crop = np.frombuffer(packet["rgb"], dtype=np.uint8).reshape(packet["h"], packet["w"], 3)
            else:
                crop = packet
            digest = hashlib.sha256(crop.tobytes()).hexdigest()
            # Include provider/model/key fingerprint, so switching config never reuses another model's result.
            scope = str((config.get("base_url"), config.get("model"), config.get("api_key"), m["type"]))
            key = digest + hashlib.sha256(scope.encode()).hexdigest()
            visual = self.cache.get(key)
            if visual is not None:
                stats["cache_hits"] += 1
            elif stats["vision_calls"] >= self.max_calls:
                m["metadata"]["recognition_status"] = "本轮识别预算已用完"
                continue
            else:
                stats["vision_calls"] += 1
                try:
                    visual = self.vision.describe(crop, config, m["type"])
                    self.cache.put(key, visual)
                except JevError as exc:
                    stats["errors"].append({"stage": "vision", "error": str(exc), "status": exc.status})
                    m["metadata"]["recognition_status"] = "视觉识别失败；保留本地结果"
                    continue
            m["metadata"]["visual"] = visual
            m["metadata"]["recognition_status"] = "已识别可见卡片 / 图片；推断与 OCR 分开"
            if m["type"] in ("image", "sticker") and visual.get("confidence", 0) >= .8:
                detected = visual.get("media_type")
                if detected in ("image", "sticker", "gif"):
                    m["type"] = detected
        stats["vision_ms"] = int((time.perf_counter()-started)*1000)
        return out, stats

