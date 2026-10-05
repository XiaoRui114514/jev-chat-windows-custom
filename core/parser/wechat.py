"""Local bubble/anchor parsing. No network, OCR engine or UI dependencies."""
import hashlib
import re
import cv2
import numpy as np

from core.message import Message, unit
from core.ocr import clean_text
from core.emoji import local_semantics, only_emoji

def rectangle(box):
    points = np.asarray(box)
    return tuple(int(x) for x in (points[:, 0].min(), points[:, 1].min(),
                                  points[:, 0].max(), points[:, 1].max()))

def inside(rect, bounds):
    x, y = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    return bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]

def fingerprint(image):
    small = cv2.resize(image, (16, 16), interpolation=cv2.INTER_AREA)
    return hashlib.sha256((small // 16).tobytes()).hexdigest()[:20]

def play_button(image):
    h, w = image.shape[:2]
    if min(h, w) < 45:
        return False
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    center = gray[int(h*.22):int(h*.72), int(w*.2):int(w*.8)]
    scale = min(h, w)
    circles = cv2.HoughCircles(center, cv2.HOUGH_GRADIENT, dp=1.2,
        minDist=scale*.18, param1=100, param2=22,
        minRadius=max(8, int(scale*.045)), maxRadius=max(12, int(scale*.17)))
    if circles is None:
        return False
    # A card thumbnail on the far right may contain circles; playback overlays
    # must be near the centre of the full media preview, not any small circle.
    return any(.35*w <= cx+w*.2 <= .65*w and .3*h <= cy+h*.22 <= .7*h
               for cx, cy, radius in circles[0])

class WeChatParser:
    def __init__(self, app):
        self.app = app
        self.avatar_names = {}  # bounded visual hints learned only with visible names
        self.boxes = []

    def regions(self, chat, pane_bg):
        h, w = chat.shape[:2]
        diff = np.abs(chat.astype(np.int16) - np.asarray(pane_bg, dtype=int)).max(axis=2)
        mask = (diff > 8).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        _, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        regions = []
        for x, y, bw, bh, area in stats[1:]:
            if bw >= 12 and bh >= 12 and area >= 100 and bw < w*.94:
                regions.append((int(x), int(y), int(x+bw), int(y+bh)))
        avatars = [b for b in regions if .7 <= (b[2]-b[0])/(b[3]-b[1]) <= 1.35
                   and 14 <= b[2]-b[0] <= min(120, w*.21)
                   and (b[0] < w*.15 or b[2] > w*.85)]
        return regions, avatars

    def parse(self, chat, pane_bg, ocr_rows):
        self.boxes = []
        h, w = chat.shape[:2]
        regions, avatars = self.regions(chat, pane_bg)
        rows = [(rectangle(box), clean_text(text), unit(score)) for box, text, score in ocr_rows]
        messages = []
        consumed = set()
        # Anchors establish side; card crops exclude avatars and neighbouring bubbles.
        for bounds in sorted(regions, key=lambda b: (b[1], b[0])):
            if bounds in avatars:
                continue
            x0, y0, x1, y1 = bounds
            bw, bh = x1-x0, y1-y0
            anchors = [a for a in avatars if abs(a[1]-y0) < max(a[3]-a[1], 12)*1.6
                       and (0 < x0-a[2] < (a[2]-a[0])*2 or 0 < a[0]-x1 < (a[2]-a[0])*2)]
            if not anchors:
                continue
            anchor = min(anchors, key=lambda a: abs(a[1]-y0))
            who = "her" if anchor[0] < x0 else "me"
            content = [(i, r) for i, r in enumerate(rows) if inside(r[0], bounds)]
            content.sort(key=lambda item: (item[1][0][1], item[1][0][0]))
            texts = [r[1] for _, r in content]
            image = chat[y0:y1, x0:x1]
            kind, confidence, meta = self.classify(image, content, bounds)
            if kind == "unknown" and not content and min(bw, bh) < 30:
                continue
            text = self.join_rows([r for _, r in content]) if kind in ("text", "emoji") else "\n".join(texts)
            # Only names directly above THIS anchor/bubble; never inherit last seen name.
            names = [r for r in rows if x0-12 <= r[0][0] < x0+bw*.6
                     and 0 <= y0-r[0][3] < (anchor[3]-anchor[1])*.85
                     and len(r[1]) <= 24 and not re.search(r"[:：]|^\d", r[1])]
            name = min(names, key=lambda r: y0-r[0][3])[1] if names and who == "her" else None
            avatar = fingerprint(chat[anchor[1]:anchor[3], anchor[0]:anchor[2]])
            if name:
                self.avatar_names[avatar] = name
                if len(self.avatar_names) > 100:
                    del self.avatar_names[next(iter(self.avatar_names))]
            # Avatar hashes are only hints, never assert identity from lookalike avatars.
            if avatar in self.avatar_names and not name:
                meta["speaker_hint"] = self.avatar_names[avatar]
                meta["speaker_hint_confidence"] = .65
            meta["avatar_bounds"] = anchor
            if local_semantics(text):
                meta["local_semantics"] = local_semantics(text)
            message = Message(who, text, kind, name, bounds=bounds,
                ocr_confidence=min((r[2] for _, r in content), default=0), sender_confidence=.94,
                type_confidence=confidence, metadata=meta).identify(fingerprint(image) if kind not in ("text", "emoji") else "")
            messages.append(message)
            consumed.update(i for i, _ in content)
            self.boxes.append(bounds + (kind, text))
        return sorted(messages, key=lambda m: (m.bounds[1], m.bounds[0])), consumed

    def join_rows(self, rows):
        if not rows:
            return ""
        groups = []
        for bounds, text, score in rows:
            if groups and abs(bounds[1]-groups[-1][0]) < max(3, (bounds[3]-bounds[1])*.4):
                sep = " " if re.search(r"[A-Za-z0-9]$", groups[-1][1]) and re.match(r"[A-Za-z0-9]", text) else ""
                groups[-1][1] += sep + text
            else:
                groups.append([bounds[1], text])
        return "\n".join(g[1] for g in groups)

    def classify(self, image, content, bounds):
        h, w = image.shape[:2]
        text = "\n".join(r[1] for _, r in content)
        bottom = [(i, r) for i, r in content if (r[0][1]-bounds[1]) > h*.73]
        meta = {"recognition_status": "未开启内容识别"}
        if re.search(r"\.(pdf|docx?|xlsx?|zip|rar|pptx?)\b", text, re.I):
            return "file", .9, meta
        if re.fullmatch(r"\s*\d+\s*[\"″'秒]\s*", text):
            return "voice", .72, meta
        play = play_button(image) if min(h, w) > 70 else False
        if play:
            # A footer author row + tall preview distinguishes channel cards from videos.
            footer = " ".join(r[1] for _, r in bottom).strip()
            if footer and h/w > 1.05:
                meta["author"] = footer
                titles = [r[1] for _, r in content if r[0][1]-bounds[1] < h*.3]
                if titles:
                    meta["title"] = " ".join(titles)
                return "video_channel", .84, meta
            return "video", .74, meta
        if bottom and w/h > 1.45 and h > 55:
            title = " ".join(r[1] for _, r in content if r[0][1]-bounds[1] < h*.65)
            source = " ".join(r[1] for _, r in bottom)
            if title:
                meta.update(title=title, source=source)
                return "article", .78, meta
        if re.search(r"https?://|www\.", text):
            return "link", .92, meta
        # Flat background is a text bubble; textured region needs cautious image handling.
        from core.ocr import dominant_color
        _, fraction = dominant_color(image)
        if content and fraction > .56:
            return ("emoji" if only_emoji(text) else "text"), .93, {}
        if re.search(r"\bGIF\b|动画表情", text, re.I):
            meta["motion_status"] = "仅截图；未验证动画帧"
            return "gif", .72, meta
        if min(w, h) > 45:
            # Transparency-like pane surround and compact square preview suggest stickers,
            # but a square photograph is not enough evidence. Keep it image/unknown.
            if fraction > .45 and .65 < w/h < 1.5 and not play:
                meta["type_uncertain"] = "疑似表情包；需视觉确认"
                return "sticker", .55, meta
            return "image", .7, meta
        return "unknown", .35, meta
