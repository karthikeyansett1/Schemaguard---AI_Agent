import pandas as pd
from engine import make_clean, inject, scan, evaluate, checks_sql, run_sql

def test_duplicate_detection():
    baseline=make_clean(); modified,_=inject(baseline,8)
    assert "duplicate_key" in {f["code"] for f in scan(modified,baseline)}

def test_benchmark_reproducible():
    a=evaluate(); b=evaluate()
    assert a["corruptions_detected"]==b["corruptions_detected"]
    assert a["corruptions_total"]==20

def test_sql_template():
    assert "duplicate_key_rows" in checks_sql()

def test_read_only_sql():
    assert len(run_sql(make_clean(),"SELECT * FROM orders LIMIT 2"))==2
