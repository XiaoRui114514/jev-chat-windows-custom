"""Exercise the packaged UI and OCR without capture, network or user settings."""
import json
from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer, qVersion
from PySide6.QtGui import QGuiApplication
from rapidocr_onnxruntime import RapidOCR

from app import settings
from app.version import VERSION


def run(report_path):
    report = Path(report_path).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    # This process exits after the check. Never read or write the user's config
    # or API keys, including keys persisted in the Windows registry.
    settings._CONFIG = str(report.with_name("smoke-config.json"))
    settings._read_env = lambda name: ""
    # Import the normal startup modules too, after isolating the settings.
    import main
    from app.debugwin import DebugWindow
    from app.overlay import Overlay

    overlay = Overlay(on_fill=lambda text: None)
    overlay.set_capture(False, "启动检查")
    overlay.app.processEvents()
    home = report.with_name(report.stem + "-home.png")
    if not overlay.win.grab().save(str(home)):
        raise RuntimeError("Could not render the main window")
    overlay.open_settings()
    overlay.app.processEvents()
    screenshot = report.with_suffix(".png")
    if not overlay.win.grab().save(str(screenshot)):
        raise RuntimeError("Could not render the settings page")
    debug = DebugWindow(on_close=lambda: None)
    debug.show()
    overlay.app.processEvents()
    reader = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
    reader(np.full((64, 256, 3), 255, dtype=np.uint8), use_cls=False)
    QTimer.singleShot(250, overlay.app.quit)
    exit_code = overlay.app.exec()
    report.write_text(json.dumps({
        "ok": exit_code == 0,
        "version": VERSION,
        "qt": qVersion(),
        "platform": QGuiApplication.platformName(),
        "ocr": "ok",
        "widgets": len(overlay.app.allWidgets()),
    }, indent=2), encoding="utf-8")
    debug.close()
    overlay.win.close()
    return exit_code
