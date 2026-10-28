import pytest

from core.draft import _parse_candidates, draft_candidates
from core.errors import JevError
from core.message import Message
from core.message.context import engine_messages


def test_annotated_context_preserves_echo_filter_and_style(monkeypatch):
    messages = engine_messages([
        Message("me", "好嘞", "text").to_dict(),
        Message("me", "晚点聊", "text").to_dict(),
        Message("her", "明天见", "text").to_dict(),
    ])
    calls = []

    def chat(*args, **kwargs):
        calls.append(args[5])
        return ('["明天见", "到时叫我", "好呀"]' if len(calls) == 1
                else '["我先去忙了"]')

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr("core.draft.chat", chat)
    result = draft_candidates(messages, "friends")

    assert result == ["到时叫我", "好呀", "我先去忙了"]
    assert "模仿用词、长短、标点习惯）：\n好嘞\n晚点聊" in calls[0][0]
    assert "可见文字（OCR）：明天见" in calls[0][0]


@pytest.mark.parametrize("content", ['[null, true, 3, {}]', '[]', '[""]'])
def test_non_text_json_candidates_are_rejected(content):
    with pytest.raises(JevError):
        _parse_candidates(content)


def test_mixed_json_candidates_only_keep_text():
    assert _parse_candidates('[null, "可以呀", {"text": "错误结构"}, "晚点见"]') == ["可以呀", "晚点见"]
    assert _parse_candidates('1. [null]\n2. "收到"\n3. [true]') == ["收到"]
