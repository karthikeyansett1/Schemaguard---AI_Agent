"""Tests tool dispatch without needing a running Ollama server.

These mock tests test Python integration only; they are not proof of model behavior.
"""
from types import SimpleNamespace
import sys
import pytest
from engine import make_clean, inject
from graph_agent import inspect, llm_investigation


class Message:
    def __init__(self, tool=None, content=''):
        self.tool_calls = ([] if tool is None else [SimpleNamespace(function=SimpleNamespace(name=tool, arguments={}))])
        self.content = content

    def model_dump(self, exclude_none=True):
        return {'role': 'assistant', 'content': self.content}


@pytest.mark.parametrize('selected_tool', ['get_quality_findings', 'get_column_profile'])
def test_readonly_tool_execution(monkeypatch, selected_tool):
    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def chat(self, **kwargs):
            if kwargs.get('tools'):
                return SimpleNamespace(message=Message(tool=selected_tool))
            return SimpleNamespace(message=Message(content='Evidence-grounded summary'))
    monkeypatch.setitem(sys.modules, 'ollama', SimpleNamespace(Client=FakeClient))
    ref = make_clean(n=200)
    corrupted, _ = inject(ref, 13)
    state = dict(inspect({'incoming': corrupted, 'reference': ref}))
    state['question'] = f'Please call {selected_tool}'
    result = llm_investigation(state)
    assert result['model_status'] == 'completed'
    assert result['tool_events'][0]['tool'] == selected_tool
    assert result['tool_events'][0]['success'] is True
    assert result['model_error'] == ''


def test_model_failure_is_not_silent(monkeypatch):
    class BrokenClient:
        def __init__(self, **kwargs): pass
        def chat(self, **kwargs): raise ConnectionError('server down')
    monkeypatch.setitem(sys.modules, 'ollama', SimpleNamespace(Client=BrokenClient))
    ref = make_clean(n=100)
    state = dict(inspect({'incoming': ref, 'reference': ref}))
    result = llm_investigation(state)
    assert result['model_status'] == 'failed'
    assert 'failed' in result['ai_notes'].lower()
