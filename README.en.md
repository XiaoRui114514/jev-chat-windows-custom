# JevChat-Windows Custom

[简体中文](README.md) · English

An independent Windows reply-assistance fork of [jev-chat/jev-chat-windows](https://github.com/jev-chat/jev-chat-windows), based on upstream v0.1.12. It captures a visible WeChat window, performs local OCR, analyzes context and offers candidate replies. Filling a reply never sends it automatically; sending remains manual.

## Install

Download the ZIP from [Releases](https://github.com/XiaoRui114514/jev-chat-windows-custom/releases), extract the entire directory and run `jev-chat-windows.exe`. Keep the bundled files together. Requires Windows 10 1903+ or Windows 11 and a visible, non-minimized chat window.

For source development use Python 3.10–3.12; the OCR dependency does not support Python 3.13+:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Models and privacy

Judging supports OpenRouter, TypeSafe and custom OpenAI-compatible or TypeSafe-compatible endpoints. Drafting has separate model settings. A compatible chat model is not the Jev model; results depend on your chosen provider/model. Provider fees may apply.

OCR runs locally, but model analysis sends the relevant recognized conversation to the configured provider. Optional image/rich-media analysis is off by default; enabling it can send cropped message images to a vision provider. Process only conversations you are authorized to access. Do not publish chat screenshots, API keys, configuration or raw logs in bug reports.

Keys use Windows current-user environment-variable slots; non-secret settings are in `config.json`. This is not an encrypted credential vault. Low-confidence OCR/sender results remain uncertain, and article/video cards expose only visible card information, not downloaded full content.

## Verify and contribute

Install the SDK/test dependencies listed in the [core test workflow](.github/workflows/tests.yml). Run `python -m pytest -q` and `python -m compileall -q app core main.py`. Windows capture, Qt and offline OCR require separate Windows acceptance. Packaged builds additionally run `tools/verify_frozen.py` before release.

Report Windows/Python/app versions and minimal reproduction steps through [Issues](https://github.com/XiaoRui114514/jev-chat-windows-custom/issues). Use synthetic messages for examples.

MIT licensed with upstream attribution and dependency notices in [LICENSE](LICENSE) and [NOTICE](NOTICE). This fork is not an official upstream release or endorsement. For the older v0.1.11 binary patch, see [custom-jev](https://github.com/XiaoRui114514/jev-chat-windows-custom-jev); new source development belongs here.
