"""Fail a build if the actual Windows executable cannot render UI and run OCR."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path, default=Path("qa-output/frozen-smoke"))
    args = parser.parse_args()
    executable = args.executable.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = output / "startup.json"
    report.unlink(missing_ok=True)
    env = dict(os.environ, QT_QPA_PLATFORM="windows")
    with tempfile.TemporaryDirectory(prefix="jev-smoke-") as cwd:
        subprocess.run([str(executable), "--smoke-test", str(report)],
                       cwd=cwd, env=env, timeout=60, check=True)
    if not report.is_file():
        raise RuntimeError("Packaged application did not finish its startup check")
    result = json.loads(report.read_text(encoding="utf-8"))
    if not (result.get("ok") and result.get("platform") == "windows"
            and result.get("ocr") == "ok" and result.get("widgets", 0) > 0):
        raise RuntimeError(f"Startup check failed: {result}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
