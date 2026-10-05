import numpy as np
from PIL import Image, ImageDraw
from app.chatapps import WECHAT
from core.parser import WeChatParser
from core.message import Message
from core.message.context import message_text
from core.message.tracker import MessageTracker
from core.ocr import clean_text
from core.emoji import only_emoji, local_semantics

def row(x,y,text,w=130,h=20):
    return ([[x,y],[x+w,y],[x+w,y+h],[x,y+h]],text,.98)

def scene(group=False):
    im = Image.new("RGB", (600, 480), (30,30,30))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((16,30,52,66),5,fill=(80,100,120))
    draw.rounded_rectangle((68,30 if not group else 52,240,90),6,fill=(255,255,255))
    draw.rounded_rectangle((16,135,52,171),5,fill=(90,110,140))
    draw.rounded_rectangle((68,135,240,177),6,fill=(255,255,255))
    draw.rounded_rectangle((548,230,584,266),5,fill=(150,80,80))
    draw.rounded_rectangle((370,230,532,275),6,fill=(149,236,105))
    return np.asarray(im)

def test_bubble_boundaries_and_sender():
    parser = WeChatParser(WECHAT)
    msgs,_ = parser.parse(scene(), (30,30,30), [row(80,40,"你好"),row(80,66,"今天有空吗"),
                                            row(80,145,"hello 123"),row(382,241,"晚上见")])
    assert len(msgs)==3
    assert [m.sender for m in msgs]==["her","her","me"]
    assert msgs[0].text=="你好\n今天有空吗"
    assert msgs[1].text=="hello 123"

def test_name_does_not_leak_to_next_avatar():
    parser=WeChatParser(WECHAT)
    msgs,_=parser.parse(scene(True),(30,30,30),[row(68,29,"张三",45,14),row(80,60,"你好"),row(80,145,"收到")])
    assert msgs[0].name=="张三"
    assert msgs[1].name is None

def test_conservative_cleanup():
    for text in ["哈哈哈哈哈哈", "666666", "hello world 123", "https://example.com/a?x=1", "😂👍"]:
        assert clean_text(text)==text
    assert clean_text("中 文 测 试")=="中文测试"
    assert only_emoji("😂👍") and local_semantics("😂")
    assert not only_emoji("你好😂")

def test_repeat_and_scroll():
    tracker=MessageTracker()
    a=Message("her","哈哈","text").identify()
    b=Message("her","收到","text").identify()
    assert len(tracker.new([a]))==1
    assert tracker.new([a])==[]
    assert len(tracker.new([a,a]))==1
    assert len(tracker.new([a,a,b]))==1
    assert tracker.new([a,b])==[]

def test_context_distinguishes_fact_and_inference():
    m=Message("her","可见标题","article",ocr_confidence=.95,sender_confidence=.9,type_confidence=.8,
              metadata={"visual":{"visual_description":"缩略图", "confidence":.6},
                        "intent":{"likely_intent":"分享", "tone":"轻松", "confidence":.5}}).to_dict()
    text=message_text(m)
    assert "OCR" in text and "视觉推断" in text and "非事实" in text
    assert "未打开正文" in text

