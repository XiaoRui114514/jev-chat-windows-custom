"""Optional local-only validation. Outputs never include original private images."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ocr import Reader

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    reader = Reader()
    for path in args.directory.glob("*截图/*.png"):
        image = np.asarray(Image.open(path).convert("RGB"))
        bg = np.median(image[:, :5].reshape(-1, 3), axis=0)
        reader.read(image, bg)
        print(json.dumps({"file": path.name, "ocr_ms": reader.last_ms, "parser_ms": reader.parser_ms,
                          "messages": [m.to_dict() for m in reader.last_messages]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
