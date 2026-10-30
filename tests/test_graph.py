import pandas as pd
from engine import make_clean, inject
from graph_agent import investigate, build_graph


def test_deterministic_graph_clean():
    ref=make_clean(n=200)
    result=investigate(ref.copy(),ref,llm_enabled=False)
    assert result["findings"] == []
    assert result["sql_validated"]
    assert [s["stage"] for s in result["stages"]] == ["inspect","diagnose","generate_sql","verify_sql","report"]
    assert "NO RULE VIOLATIONS" in result["report"]


def test_graph_detects_duplicate_without_model():
    ref=make_clean()
    corrupt, truth=inject(ref,8)
    result=investigate(corrupt,ref,llm_enabled=False)
    assert any(f["code"] == truth for f in result["findings"])
    assert "REVIEW REQUIRED" in result["report"]


def test_graph_branches():
    ref=make_clean(n=200)
    from graph_agent import route
    assert route({"llm_enabled":True}) == "llm_investigation"
    assert route({"llm_enabled":False}) == "deterministic_investigation"
