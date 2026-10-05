from unittest.mock import patch
from core.engine import analyze
from core.errors import JevError

def test_judge_draft_rank_and_base_forwarding():
    with patch("core.engine.ask",side_effect=[{"answers":{"a":{"noul":.8}},"usage":{"input_tokens":2}},
            {"answers":{"best_reply":{"choice":"reply_b","probabilities":{"reply_b":.9}}},"usage":{"input_tokens":3}}]) as ask, \
         patch("core.engine.draft_candidates",return_value=["A","B","C"]) as draft:
        result=analyze([("her","你好")],"friends",jev_provider="custom_openai",jev_model="m",jev_base_url="https://example.com/v1")
        assert result["best_reply"]=="B" and result["usage"]["input_tokens"]==5
        assert all(call.kwargs["base_url"]=="https://example.com/v1" for call in ask.call_args_list)
        assert draft.call_args.kwargs["guidance"] is not None

def test_fallback_and_rank_failure():
    with patch("core.engine.ask",side_effect=[JevError("judge failed"),{"answers":{},"usage":{}}]), \
         patch("core.engine.draft_candidates",return_value=["A","B","C"]):
        result=analyze([("her","hello")],"friends")
        assert result["best_reply"]=="A" and result["diagnostics"][0]["stage"]=="judge"
    with patch("core.engine.ask",side_effect=[{"answers":{},"usage":{}},JevError("rank failed")]), \
         patch("core.engine.draft_candidates",return_value=["A","B","C"]):
        assert analyze([("her","hello")],"friends")["best_reply"]=="A"
