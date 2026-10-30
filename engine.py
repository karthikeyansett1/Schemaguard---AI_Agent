"""Deterministic CSV quality checks and evaluation. Never uses LLM for detection."""
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

RULES = {"order_id":"unique identifier", "customer_id":"required text", "amount":"nonnegative money", "quantity":"positive integer", "region":"known category"}
KNOWN_REGIONS = {"North", "South", "East", "West"}

def make_clean(seed=13, n=1000):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "order_id": np.arange(10000,10000+n),
        "customer_id": [f"C{v:04d}" for v in rng.integers(0,200,n)],
        "amount": rng.gamma(4,25,n).round(2),
        "quantity": rng.integers(1,8,n),
        "region": rng.choice(sorted(KNOWN_REGIONS),n),
    })

def profile(df):
    return pd.DataFrame({"column":df.columns,"dtype":[str(t) for t in df.dtypes],
        "missing":df.isna().sum().values,"missing_pct":(df.isna().mean()*100).round(2).values,
        "unique":df.nunique(dropna=True).values})

def scan(df, reference, key="order_id"):
    findings=[]
    def flag(code, column, detail, severity="high"):
        findings.append({"code":code,"column":column,"severity":severity,"detail":detail})
    for col in reference.columns.difference(df.columns):
        flag("schema_missing", col, "Reference column is missing")
    for col in df.columns.difference(reference.columns):
        flag("schema_extra", col, "Unexpected incoming column", "medium")
    for col in df.columns.intersection(reference.columns):
        if str(df[col].dtype)!=str(reference[col].dtype):
            flag("schema_dtype",col,f"Expected {reference[col].dtype}; got {df[col].dtype}")
        new_null=df[col].isna().mean(); old_null=reference[col].isna().mean()
        if new_null > max(.05, old_null+.05):
            flag("null_spike",col,f"Null rate {new_null:.1%} vs {old_null:.1%}")
    if key in df:
        duplicated=int(df[key].duplicated(keep=False).sum())
        if duplicated: flag("duplicate_key",key,f"{duplicated} rows have duplicated keys")
    if "amount" in df:
        values=pd.to_numeric(df["amount"],errors="coerce")
        invalid=int(((values<0)|(values>10000)).sum())
        if invalid: flag("invalid_amount","amount",f"{invalid} values outside [0, 10000]")
    if "quantity" in df:
        values=pd.to_numeric(df["quantity"],errors="coerce")
        invalid=int(((values<=0)|(values>100)|(values.notna() & (values%1!=0))).sum())
        if invalid: flag("invalid_quantity","quantity",f"{invalid} impossible quantities")
    if "region" in df:
        unknown=set(df["region"].dropna().astype(str))-KNOWN_REGIONS
        if unknown: flag("unknown_category","region",f"Unexpected categories: {sorted(unknown)[:5]}")
    for col in ["amount", "quantity"]:
        if col not in df or col not in reference: continue
        a=pd.to_numeric(df[col],errors="coerce").dropna()
        b=pd.to_numeric(reference[col],errors="coerce").dropna()
        if len(a)<30 or len(b)<30: continue
        stat,p=ks_2samp(a,b)
        if p < .001 and stat > .15:
            flag("distribution_shift",col,f"KS statistic={stat:.3f}, p={p:.2g}","medium")
    return findings

def checks_sql(table="orders"):
    # table intentionally fixed allowlist: SQL text is a generated template, not executed.
    if table not in ("orders", "staging_orders"):
        raise ValueError("Only orders or staging_orders are supported as SQL table names")
    return f"""-- Checks return a violation count. Expect zero.
SELECT COUNT(*) AS duplicate_key_rows FROM (SELECT order_id FROM {table} GROUP BY order_id HAVING COUNT(*) > 1);
SELECT COUNT(*) AS invalid_amount FROM {table} WHERE amount < 0 OR amount > 10000;
SELECT COUNT(*) AS invalid_quantity FROM {table} WHERE quantity <= 0 OR quantity > 100 OR quantity <> FLOOR(quantity);
SELECT COUNT(*) AS missing_customer FROM {table} WHERE customer_id IS NULL;
SELECT COUNT(*) AS unknown_region FROM {table} WHERE region NOT IN ('East','West','North','South');"""

def inject(reference, case):
    """20 reproducible single-family corruption cases, 4 each across 5 categories."""
    df=reference.copy(deep=True); subtype=case%4; family=case//4
    idx=np.arange(30+subtype*15)
    if family==0:
        df.loc[idx,"customer_id"]=None; label="null_spike"
    elif family==1:
        if subtype%2==0: df["unexpected_field"]=case; label="schema_extra"
        else: df=df.drop(columns=["customer_id"]); label="schema_missing"
    elif family==2:
        df.loc[idx,"order_id"]=df.loc[idx+100,"order_id"].to_numpy(); label="duplicate_key"
    elif family==3:
        if subtype%2==0:
            df.loc[idx,"amount"]=-100; label="invalid_amount"
        else:
            df.loc[idx,"quantity"]=0; label="invalid_quantity"
    else:
        df["amount"]=df["amount"]*(3.0+subtype*.4); label="distribution_shift"
    return df,label

def evaluate(reference=None):
    reference=make_clean() if reference is None else reference
    cases=[]
    for i in range(20):
        altered,label=inject(reference,i)
        found={x["code"] for x in scan(altered,reference)}
        cases.append({"case":i+1,"truth":label,"detected":label in found,"all_flags":", ".join(sorted(found))})
    # 20 independent clean snapshots: count flags by snapshot, not by rows
    false_positives=[]
    for i in range(20):
        clean=make_clean(seed=100+i)
        flags=scan(clean,reference)
        false_positives.append({"case":i+1,"flagged":bool(flags),"flags":", ".join(f["code"] for f in flags)})
    hit=sum(c["detected"] for c in cases)
    fp=sum(c["flagged"] for c in false_positives)
    return {"recall":hit/20,"clean_snapshot_false_positive_rate":fp/20,
            "corruptions_detected":hit,"corruptions_total":20,
            "cases":pd.DataFrame(cases),"clean_cases":pd.DataFrame(false_positives)}


def run_sql(df, query):
    """Read-only SQL against the in-memory 'orders' table (no disk / network)."""
    import re
    import sqlite3
    sql=query.strip()
    if not re.match(r"^SELECT\s", sql, flags=re.I):
        raise ValueError("Only SELECT queries are allowed")
    if ";" in sql or "--" in sql or "/*" in sql:
        raise ValueError("Multi-statement SQL and comments are not allowed")
    forbidden=r"\b(read_csv|read_parquet|read_json|copy|attach|install|load|pragma|httpfs|sqlite_scan|postgres_scan|query|from_csv_auto)\b"
    if re.search(forbidden,sql,flags=re.I):
        raise ValueError("Restricted operation")
    con=sqlite3.connect(":memory:")
    try:
        df.to_sql("orders",con,index=False,if_exists="replace")
        con.set_authorizer(lambda action,*args: sqlite3.SQLITE_OK if action in
            (sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION) else sqlite3.SQLITE_DENY)
        return pd.read_sql_query("SELECT * FROM ("+sql+") AS safe_result LIMIT 100", con)
    finally:
        con.close()
