from concurrent.futures import CancelledError
import pytest
from core.engine import analyze
from core.errors import _api_key, credential_snapshot, redact_secrets

def test_cancel_after_judge_prevents_draft_and_rank(monkeypatch):
    calls=[]
    monkeypatch.setattr('core.engine.ask',lambda *a,**k: calls.append('judge') or {'answers':{}})
    monkeypatch.setattr('core.engine.draft_candidates',lambda *a,**k: calls.append('draft') or ['hi'])
    def checkpoint(stage):
        if stage=='起草': raise CancelledError()
    with pytest.raises(CancelledError): analyze([('her','hello')],'friends',checkpoint=checkpoint)
    assert calls==['judge']

def test_snapshot_keeps_old_credentials_and_redacts_after_environment_change(monkeypatch):
    monkeypatch.setenv('JEV_API_KEY','new-key')
    with credential_snapshot({'JEV_API_KEY':'original-task-key'}):
        assert _api_key()=='original-task-key'
        assert 'original-task-key' not in redact_secrets('original-task-key new-key')
    assert _api_key()=='new-key'
