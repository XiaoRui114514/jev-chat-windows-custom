"""Exercise actual main.py orchestration with only Windows/Qt boundaries replaced."""
import importlib.util
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import app


def test_desktop_coalesces_each_chat_cancels_stale_and_freezes_configuration(monkeypatch):
    for name, fields in {'worker':{'run':None}, 'capture':{'find_chat_hwnd':None}, 'fill':{'fill':None}, 'overlay':{'Overlay':None}}.items():
        stub=SimpleNamespace(**fields)
        monkeypatch.setitem(sys.modules,'app.'+name,stub)
        monkeypatch.setattr(app,name,stub,raising=False)
    spec=importlib.util.spec_from_file_location('desktop_orchestration_test',Path(__file__).resolve().parents[1]/'main.py')
    main=importlib.util.module_from_spec(spec);spec.loader.exec_module(main)
    values={'has_jev_key':True,'has_llm_key':True,'reply_target':False,'relationship':'friends','context':10,'style':'',
            'thinking':False,'jev_provider':'openrouter','jev_model':'jev','jev_base_url':'','draft_provider':'deepseek',
            'draft_model':'original-model','draft_base_url':'','recognition':{'emoji_intent':False},'vision_config':{},
            'jev_key':'test-judge','llm_key':'test-draft'}
    main.settings=SimpleNamespace(**{k:(lambda name=k:values[name]) for k in values})
    main.ov=SimpleNamespace(set_busy=lambda *a:None,set_status=lambda *a:None,current_chat=lambda:'A',after=lambda *a:None,forget_chat=lambda *a:None)
    created=[]
    class Deferred:
        def __init__(self,**kwargs): self.args=kwargs['args'];created.append(self)
        def start(self): pass
    main.threading=SimpleNamespace(Thread=Deferred,Event=threading.Event)
    main.drain=lambda:None
    main.start_analyze('A',[{'from':'her','text':'a'}])
    first=created[0]
    values['draft_model']='changed-model'
    assert first.args[5]['model']=='original-model'
    for title,text in [('B','old'),('C','other'),('B','new')]:
        main.start_analyze(title,[{'from':'her','text':text}])
    assert list(main.pending)==['B','C']
    assert main.pending['B'][0]['text']=='new'
    assert main.active_cancel.is_set()
    main.results.put(('cancel','', 'A',0));main.tick()
    assert main.active_title=='B' and list(main.pending)==['C']
    assert created[1].args[5]['model']=='changed-model'
    assert created[1].args[0][0]['text']=='new'
