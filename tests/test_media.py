import numpy as np
import pytest
from core.media import MediaAnalyzer
from core.media.cache import TTLCache
from core.errors import JevError
from core.emoji.intent import EmojiIntentAnalyzer

class Vision:
    def __init__(self): self.calls=0
    def describe(self,crop,config,kind):
        self.calls+=1
        assert crop.shape==(40,50,3)
        return {"visual_description":"可见缩略图", "confidence":.8,"media_type":kind}

def message(kind="article"):
    return {"id":"a","from":"her","type":kind,"sender_confidence":.9,"metadata":{}}

@pytest.mark.parametrize("kind",["article","video_channel","link","image","sticker","gif","text","emoji","unknown"])
def test_disabled_never_calls_vision(kind):
    vision=Vision()
    analyzer=MediaAnalyzer(vision)
    _,stats=analyzer.enrich([message(kind)],{"a":np.zeros((40,50,3),np.uint8)},{},{})
    assert vision.calls==stats["vision_calls"]==0

def test_selected_crop_cache_and_gate():
    vision=Vision(); analyzer=MediaAnalyzer(vision)
    crops={"a":np.zeros((40,50,3),np.uint8)}
    out,stats=analyzer.enrich([message()],crops,{"article":True},{"model":"m"})
    assert vision.calls==1 and out[0]["metadata"]["visual"]["confidence"]==.8
    _,stats=analyzer.enrich([message()],crops,{"article":True},{"model":"m"})
    assert vision.calls==1 and stats["cache_hits"]==1
    analyzer.enrich([message("image")],crops,{"article":True},{})
    assert vision.calls==1
    analyzer.enrich([{**message(),"sender_confidence":.2}],crops,{"article":True},{})
    assert vision.calls==1

def test_ttl_and_limit():
    now=[0]; cache=TTLCache(limit=2,ttl=10,clock=lambda:now[0])
    cache.put("a",1);cache.put("b",2);cache.put("c",3)
    assert cache.get("a") is None
    now[0]=11
    assert cache.get("b") is None

def test_vision_failure_preserves_local():
    class Bad:
        def describe(self,*args): raise JevError("模型不支持视觉",400)
    out,stats=MediaAnalyzer(Bad()).enrich([message()],{"a":np.zeros((40,50,3),np.uint8)}, {"article":True},{})
    assert out[0]["type"]=="article"
    assert stats["errors"][0]["status"]==400

def test_emoji_intent_off_or_plain_text_no_calls(monkeypatch):
    def fail(**kwargs): raise AssertionError("unexpected API call")
    monkeypatch.setattr("core.llm.chat",fail)
    analyzer=EmojiIntentAnalyzer()
    for enabled,kind in [(False,"sticker"),(True,"text")]:
        _,stats=analyzer.enrich([message(kind)],enabled,{})
        assert stats["intent_calls"]==0

def test_emoji_intent_separate_context_call(monkeypatch):
    seen=[]
    def chat(**kwargs):
        seen.append(kwargs)
        return '{"likely_intent":"无奈式吐槽", "tone":"调侃", "confidence":0.87}'
    monkeypatch.setattr("core.llm.chat",chat)
    msg=message("sticker");msg["metadata"]={"visual":{"visual_description":"人物捂脸","confidence":.9}}
    out,stats=EmojiIntentAnalyzer().enrich([msg],True,{})
    assert out[0]["metadata"]["intent"]["confidence"]==.87
    assert "人物捂脸" in seen[0]["user_turns"][0]
    assert stats["intent_calls"]==1
