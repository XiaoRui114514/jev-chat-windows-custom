import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch
import pytest

from core.jev_client import ask, list_models, JevError
from core.providers.answers import _answers_of, _answer_of
from core.providers.transport import _norm_base, _post_json
from core.media.vision import OpenAIVision

QUESTIONS={"a":{"type":"noul"},"b":{"type":"choice","criteria":{"yes":"Y","no":"N"}},
           "c":{"type":"score","criteria":["low","high"]}}
ANSWERS={"a":{"noul":.9},"b":{"choice":"yes","confidence":.8,"probabilities":{"yes":.8,"no":.2}},
         "c":{"score":1,"confidence":.7}}

@pytest.fixture
def server():
    state={"status":200,"body":None,"requests":[]}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): return
        def send(self,body):
            self.send_response(state["status"])
            self.send_header("Content-Type","application/json")
            self.end_headers()
            self.wfile.write((body if isinstance(body,str) else json.dumps(body)).encode())
        def do_GET(self):
            state["requests"].append((self.path,None))
            self.send(state["body"] if state["body"] is not None else {"data":[{"id":"m"},{"id":"m"},{"id":"vision"}]})
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append((self.path,data))
            self.send(state["body"] if state["body"] is not None else {"id":"chat-test", "object":"chat.completion", "created":1,"model":"m",
                "choices":[{"index":0,"message":{"role":"assistant","content":json.dumps({"answers":ANSWERS})},"finish_reason":"stop"}],
                "usage":{"prompt_tokens":4,"completion_tokens":6,"total_tokens":10}})
    http=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    yield f"http://127.0.0.1:{http.server_port}/v1",state
    http.shutdown();http.server_close();thread.join()

def test_custom_openai_contract(server,monkeypatch):
    base,state=server
    monkeypatch.setenv("JEV_API_KEY","test-key")
    got=ask({"chat":{}},QUESTIONS,provider="custom_openai",model="m",base_url=base)
    assert got["answers"]["b"]["choice"]=="yes"
    assert got["usage"]=={"input_tokens":4,"output_tokens":6}
    assert list_models("custom_openai","test-key",base_url=base)==["m","vision"]
    assert state["requests"][0][0]=="/v1/chat/completions"
    assert state["requests"][1][0]=="/v1/models"

@pytest.mark.parametrize("code",[401,429,400,500])
def test_http_failures_redact_and_hide_body(server,monkeypatch,code):
    base,state=server;state["status"]=code;state["body"]={"error":{"message":"test-key private conversation"}}
    monkeypatch.setenv("JEV_API_KEY","test-key")
    with pytest.raises(JevError) as exc:
        ask({},QUESTIONS,provider="custom_openai",model="m",base_url=base,timeout=1)
    assert exc.value.status==code
    assert "test-key" not in str(exc.value) and "private conversation" not in str(exc.value)

@pytest.mark.parametrize("body",["not json",{"choices":[]},{"choices":[{"message":{"content":""}}]},
    {"choices":[{"message":{"content":"{}"}}]}, {"choices":[{"message":{"content":"[]"}}]}])
def test_invalid_or_empty_returns(server,monkeypatch,body):
    base,state=server;state["body"]=body
    monkeypatch.setenv("JEV_API_KEY","test-key")
    with pytest.raises(JevError):
        ask({},QUESTIONS,provider="custom_openai",model="m",base_url=base)

def test_partial_json_fences_and_invalid_scores():
    body={"choices":[{"message":{"content":"```json\n"+json.dumps({"answers":{"a":{"noul":"0.8"},"b":{"choice":"bad"}}})+"\n```"}}]}
    assert set(_answers_of(QUESTIONS,body))=={"a"}
    for value in [float("nan"),float("inf"),True,10,-1,.5,10**400]:
        assert _answer_of(QUESTIONS["c"],{"score":value}) is None

@pytest.mark.parametrize("base",["", "xxx", "https://user:key@example.com", "https://example.com?key=k"])
def test_bad_base(base):
    with pytest.raises(JevError): _norm_base(base)

def test_typesafe_custom_and_official(monkeypatch):
    seen=[]
    class Fake:
        def __init__(self,**kwargs): seen.append(kwargs)
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def system_one(self,*args,**kwargs):
            return SimpleNamespace(answers={"a":SimpleNamespace(type="noul",noul=.8)},usage=SimpleNamespace(input_tokens=1,output_tokens=2))
        @property
        def models(self): return SimpleNamespace(list=lambda:SimpleNamespace(models=[SimpleNamespace(name="jev")]))
    monkeypatch.setenv("JEV_API_KEY","test-key")
    with patch("typesafe_sdk.TypeSafeClient",Fake):
        assert ask({},QUESTIONS,provider="custom_typesafe",model="jev",base_url="https://mirror.example")["answers"]["a"]["noul"]==.8
        assert seen[-1]["base_url"]=="https://mirror.example"
        ask({},QUESTIONS,provider="typesafe")
        assert seen[-1]["base_url"]=="https://api.typesafe.ai"
        assert list_models("custom_typesafe","k",base_url="https://mirror.example")==["jev"]

def test_timeout_and_connection(monkeypatch):
    import openai
    import httpx2
    class Fake:
        def __init__(self,**kwargs): raise openai.APITimeoutError(request=httpx2.Request("POST","https://example.com"))
    with patch("openai.OpenAI",Fake):
        monkeypatch.setenv("JEV_API_KEY","test-key")
        with pytest.raises(JevError,match="超时"):
            ask({},QUESTIONS,provider="custom_openai",model="m",base_url="https://example.com")
    with pytest.raises(JevError):
        list_models("custom_openai","test-key",timeout=.2,base_url="http://127.0.0.1:1/v1")

def test_vision_upload_is_crop_and_unsupported_model(server):
    import numpy as np
    base,state=server
    state["body"]={"choices":[{"index":0,"message":{"role":"assistant","content":json.dumps({"visual_description":"卡片", "confidence":.8,"media_type":"article"})}}]}
    config={"base_url":base,"api_key":"test-key","model":"vision"}
    got=OpenAIVision().describe(np.zeros((40,50,3),np.uint8),config,"article")
    content=state["requests"][-1][1]["messages"][-1]["content"]
    assert got["confidence"]==.8
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    state["status"]=400
    with pytest.raises(JevError,match="视觉识别"):
        OpenAIVision().describe(np.zeros((40,50,3),np.uint8),config,"article")

def test_decisions_json_and_error(monkeypatch):
    from io import BytesIO
    import urllib.error
    monkeypatch.setattr("urllib.request.urlopen",lambda *a,**kw:BytesIO(b"not-json"))
    with pytest.raises(JevError,match="JSON"):
        _post_json("https://example.com","k",{},1)
    def bad(*a,**kw): raise urllib.error.HTTPError("url",401,"bad",{},BytesIO(b"private"))
    monkeypatch.setattr("urllib.request.urlopen",bad)
    with pytest.raises(JevError,match="401"):
        _post_json("https://example.com","k",{},1)
