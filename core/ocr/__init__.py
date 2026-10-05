"""Conservative OCR utilities. Never rewrite vocabulary or collapse laughter."""
import re
import numpy as np

def clean_text(text):
    text = str(text).replace("\u200b", "").replace("\ufeff", "").strip()
    # Preserve URL, English spacing, numbers, punctuation, emoji and repetitions.
    return re.sub(r"(?<=[\u4e00-\u9fff]) +(?=[\u4e00-\u9fff])", "", text)

def dominant_color(region):
    if not region.size:
        return np.zeros(3, dtype=int), 0.0
    # Tolerates slight resampling noise; avoids thousands of unique RGB sorts.
    pixels = region.reshape(-1, 3).astype(int)
    bins = pixels // 8
    codes = bins[:, 0] * 1024 + bins[:, 1] * 32 + bins[:, 2]
    counts = np.bincount(codes, minlength=32768)
    selected = codes == counts.argmax()
    return np.median(pixels[selected], axis=0).astype(int), float(selected.mean())

def prepare(image, enlarge=False):
    if not enlarge:
        return image, 1.0
    import cv2
    return cv2.resize(image, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC), 1.5

