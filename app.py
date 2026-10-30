"""SchemaGuard AI / Command Center UI.

Drop-in replacement for the existing SchemaGuard portfolio project.
Requires the existing engine.py and graph_agent.py unchanged.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from engine import make_clean, scan, profile, evaluate, checks_sql, run_sql
from graph_agent import investigate

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="SchemaGuard | Command Center", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")
style_path = ROOT / "assets" / "command_center.css"
if style_path.exists():
    st.markdown(f"<style>{style_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

COLORS = {"cyan": "#39D9F2", "purple": "#A78BFA", "red": "#FB7185", "green": "#34D399", "muted": "#94A3B8"}
NAV = ["Overview", "Quality Monitor", "AI Investigator", "Evaluation Lab", "SQL Workspace", "Reports"]


def title_block(kicker: str, title: str, subtitle: str) -> None:
    # Static strings are authored by the app, not uploaded content.
    st.markdown(
        f'<div class="section-heading"><div class="eyebrow">{kicker}</div>'
        f'<h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True
    )


def panel_heading(title: str, caption: str = "") -> None:
    st.markdown(f"#### {title}")
    if caption:
        st.caption(caption)


def source_fingerprint(uploaded, reference_uploaded) -> str:
    h = hashlib.sha256()
    for label, file in (("incoming", uploaded), ("reference", reference_uploaded)):
        h.update(label.encode())
        h.update(file.getvalue() if file is not None else b"builtin-demo")
    return h.hexdigest()


@st.cache_data(show_spinner=False)
def load_uploaded(csv_bytes: bytes) -> pd.DataFrame:
    from io import BytesIO
    return pd.read_csv(BytesIO(csv_bytes))


@st.cache_data(show_spinner=False)
def benchmark() -> dict:
    return evaluate()


@st.cache_data(ttl=10, show_spinner=False)
def ollama_online() -> bool:
    try:
        with urlopen("http://localhost:11434/api/tags", timeout=0.65) as resp:
            return resp.status == 200
    except Exception:
        return False


def plot_format(fig, height=320):
    fig.update_layout(
        height=height, margin=dict(l=10, r=8, t=14, b=6),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#B6C7DD", size=12),
        xaxis=dict(gridcolor="#20314A", zeroline=False),
        yaxis=dict(gridcolor="#20314A", zeroline=False),
        legend=dict(orientation="h", y=1.13, x=0),
    )
    return fig


def metrics(df: pd.DataFrame, findings: list[dict]) -> None:
    high = sum(str(f.get("severity", "")).lower() == "high" for f in findings)
    missing = int(df.isna().sum().sum())
    cols = st.columns(4)
    for col, label, value, help_text in zip(
        cols,
        ["ROWS SCANNED", "COLUMNS", "QUALITY ALERTS", "NULL CELLS"],
        [f"{len(df):,}", len(df.columns), len(findings), f"{missing:,}"],
        ["Incoming dataset", "Incoming schema", f"{high} high-severity alerts", "Across all cells"],
    ):
        with col:
            st.metric(label, value, help=help_text)


with st.sidebar:
    st.markdown('<div class="brand-mark">◈ &nbsp; SCHEMAGUARD <span>AI</span></div>', unsafe_allow_html=True)
    st.caption("DATA RELIABILITY COMMAND CENTER")
    st.divider()
    section = st.radio("Navigation", NAV, key="nav", label_visibility="collapsed")
    st.divider()
    st.markdown('<div class="eyebrow">DATA SOURCE</div>', unsafe_allow_html=True)
    upload = st.file_uploader("Incoming CSV", type=["csv"], key="incoming_csv", help="Upload the snapshot you want to investigate.")
    refupload = st.file_uploader("Reference CSV", type=["csv"], key="reference_csv", help="Upload a trusted reference snapshot for comparison.")
    st.caption("No uploads? Built-in synthetic sample data is used.")
    st.divider()
    ready = ollama_online()
    st.markdown("**Local model status**")
    if ready:
        st.success("Ollama endpoint reachable")
    else:
        st.info("Demo-only mode · Ollama unavailable")
    if st.button("Refresh model status", width="stretch"):
        ollama_online.clear()
        st.rerun()
    st.caption("Public visitors can use analytics and deterministic LangGraph without a paid API.")

try:
    incoming = load_uploaded(upload.getvalue()) if upload else make_clean(seed=55)
    reference = load_uploaded(refupload.getvalue()) if refupload else make_clean()
    if incoming.empty or reference.empty:
        raise ValueError("CSV cannot be empty")
    if len(incoming) > 200_000 or len(incoming.columns) > 100:
        raise ValueError("Demo supports at most 200,000 rows and 100 columns")
    findings = scan(incoming, reference)
    health = profile(incoming)
except Exception as exc:
    st.error(f"Unable to load or inspect dataset: {type(exc).__name__}: {exc}")
    st.stop()

fingerprint = source_fingerprint(upload, refupload)
source_label = "Uploaded CSV" if upload else "Synthetic demo data"
ref_label = "Uploaded baseline" if refupload else "Synthetic baseline"

st.markdown('<div class="topbar"><span>◉ SYSTEM ONLINE</span><span>SCHEMAGUARD / OPERATIONS TERMINAL</span></div>', unsafe_allow_html=True)

if section == "Overview":
    title_block("01 / OPERATIONS OVERVIEW", "Data reliability, at a glance", "Monitor incoming data, validation health, and investigation readiness.")
    st.info(f"**Input:** {source_label} · **Reference:** {ref_label} · Synthetic examples are not production data.")
    metrics(incoming, findings)
    left, right = st.columns([1.25, 1], gap="large")
    with left:
        panel_heading("Column completeness", "Percentage of missing values in the current snapshot")
        missing_view = health[["column", "missing_pct"]].copy()
        fig = px.bar(missing_view, x="column", y="missing_pct", color_discrete_sequence=[COLORS["cyan"]])
        fig.update_yaxes(title="Missing (%)", rangemode="tozero")
        st.plotly_chart(plot_format(fig), width="stretch")
        if int(health["missing"].sum()) == 0:
            st.caption("All columns have zero nulls in this snapshot.")
    with right:
        panel_heading("Alert severity", "Rule-based results; not LLM-generated findings")
        counts = pd.Series([f.get("severity", "unknown") for f in findings]).value_counts()
        if counts.empty:
            st.success("No violations detected under the configured rules.")
            st.caption("Absence of flags is not proof of clean data.")
        else:
            severity = pd.DataFrame({"Severity": counts.index, "Count": counts.values})
            fig = px.bar(severity, x="Severity", y="Count", color="Severity",
                         color_discrete_map={"high": COLORS["red"], "medium": COLORS["purple"]})
            st.plotly_chart(plot_format(fig), width="stretch")
    st.markdown("#### Latest quality events")
    if findings:
        st.dataframe(pd.DataFrame(findings), hide_index=True, width="stretch")
    else:
        st.success("No quality alerts in the current snapshot.")

elif section == "Quality Monitor":
    title_block("02 / DATA OBSERVABILITY", "Quality Monitor", "Explore schema, missingness, cardinality and rule violations.")
    metrics(incoming, findings)
    c1, c2 = st.columns([1.1, 1], gap="large")
    with c1:
        panel_heading("Column profile")
        st.dataframe(health, hide_index=True, width="stretch")
    with c2:
        panel_heading("Missing values (%)")
        fig = px.bar(health, x="missing_pct", y="column", orientation="h", color_discrete_sequence=[COLORS["purple"]])
        fig.update_xaxes(title="Null rate (%)")
        st.plotly_chart(plot_format(fig), width="stretch")
    panel_heading("Rule findings")
    if findings:
        st.dataframe(pd.DataFrame(findings), hide_index=True, width="stretch")
    else:
        st.success("No configured rule violations. Continue monitoring.")
    with st.expander("Preview incoming data (first 25 rows)"):
        st.dataframe(incoming.head(25), hide_index=True, width="stretch")

elif section == "AI Investigator":
    title_block("03 / AGENT ORCHESTRATION", "AI Investigator", "Inspect the LangGraph execution pipeline and verified model tool calls.")
    st.info(f"**Current dataset:** {source_label} ({len(incoming):,} rows). Deterministic mode is free; LLM mode requires local Ollama.")
    left, right = st.columns([1, 1.4], gap="large")
    with left:
        use_llm = st.toggle("Enable local Qwen3 8B", value=False, disabled=not ready)
        st.caption("Model path" if use_llm else "Deterministic path")
        examples = {
            "Quality risk investigation": "Call get_quality_findings. Summarize verified violations and potential ETL impacts. Do not invent numerical constraints.",
            "Column profile / missingness": "Call get_column_profile. Report each column's dtype, missing count and unique count. Identify unknowns.",
            "Benchmark audit": "Call get_baseline_evaluation. Explain synthetic recall and clean control false-positive rate, with caveats.",
        }
        selected = st.selectbox("Investigation scenario", list(examples))
        question = st.text_area("Investigation instruction", value=examples[selected], height=150)
        execute = st.button("▶ RUN INVESTIGATION", type="primary", width="stretch")
        if execute:
            with st.spinner("Running LangGraph workflow and collecting tool events..."):
                try:
                    output = investigate(incoming, reference, question, llm_enabled=use_llm)
                    st.session_state["run"] = {
                        "output": output,
                        "fingerprint": fingerprint,
                        "question": question,
                        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                        "mode": "Ollama" if use_llm else "Deterministic",
                    }
                except Exception as exc:
                    st.error(f"Workflow failed: {type(exc).__name__}: {exc}")
        st.markdown("#### Execution architecture")
        st.code("inspect → route → investigate → generate_sql → verify_sql → report", language=None)
    with right:
        saved = st.session_state.get("run")
        if not saved:
            st.info("No investigation yet. Run a scenario to view the agent transcript and graph stages.")
        elif saved["fingerprint"] != fingerprint:
            st.warning("Dataset changed after this run. Clear and rerun to avoid showing stale evidence.")
            if st.button("Clear old investigation"):
                st.session_state.pop("run", None)
                st.rerun()
        else:
            result = saved["output"]
            mode = saved["mode"]
            status = result.get("model_status", "unknown")
            st.markdown(f"**Execution mode:** `{mode}` &nbsp; | &nbsp; **Model status:** `{status}`")
            if status == "failed":
                st.error("Local model failed. Any rule-based data-quality evidence remains separate from the LLM response.")
            elif status == "completed_without_tools":
                st.warning("Model answered without executing tools; do not treat this as verified tool-grounded reasoning.")
            elif status == "completed":
                st.success("LLM investigation completed. Check the executed tool trace.")
            else:
                st.info("Deterministic workflow completed or model outcome is incomplete.")
            st.markdown(result.get("report", "No report returned."))
            with st.expander("Execution timeline", expanded=True):
                stages = result.get("stages", [])
                if stages:
                    st.dataframe(pd.DataFrame(stages), hide_index=True, width="stretch")
                else:
                    st.info("No stage data returned")
            with st.expander("Actual tool-call events", expanded=True):
                events = result.get("tool_events", [])
                st.json(events)
                if not events:
                    st.caption("No recorded tool calls. This is expected for deterministic mode.")
            with st.expander("Generated SQL checks"):
                st.code(result.get("sql", ""), language="sql")
                st.caption(f"Template shape verified: {result.get('sql_validated', False)} — not executed against production data.")
            st.download_button("↓ Download investigation report", result.get("report", ""),
                               file_name="schemaguard_investigation.md", mime="text/markdown", width="stretch")
            payload = {
                "captured_at_utc": saved["captured_at_utc"], "mode": mode,
                "question": saved["question"], "dataset_fingerprint_sha256": fingerprint,
                "model_status": status, "stages": result.get("stages", []),
                "tool_events": result.get("tool_events", []),
                "rule_findings": result.get("findings", []),
                "sql_template_validated": result.get("sql_validated", False),
                "disclaimer": "Tool events are individual observed calls; this is not production accuracy."
            }
            st.download_button("↓ Export agent_trace.json", json.dumps(payload, indent=2, default=str),
                               file_name="agent_trace.json", mime="application/json", width="stretch")

elif section == "Evaluation Lab":
    title_block("04 / RELIABILITY ENGINEERING", "Evaluation Lab", "Measure detection-rule performance against reproducible synthetic corruptions.")
    results = benchmark()
    c1, c2, c3 = st.columns(3)
    c1.metric("INJECTED CASES DETECTED", f"{results['corruptions_detected']}/{results['corruptions_total']}")
    c2.metric("INJECTED CASE RECALL", f"{results['recall']:.0%}")
    c3.metric("CLEAN SNAPSHOT FLAG RATE", f"{results['clean_snapshot_false_positive_rate']:.0%}")
    cases = results["cases"].copy()
    cases["Outcome"] = cases["detected"].map({True: "Detected", False: "Missed"})
    agg = cases.groupby(["truth", "Outcome"]).size().reset_index(name="Count")
    panel_heading("Detection by corruption family", "Synthetic rule evaluation, not an LLM benchmark")
    fig = px.bar(agg, x="truth", y="Count", color="Outcome", barmode="stack",
                 color_discrete_map={"Detected": COLORS["cyan"], "Missed": COLORS["red"]})
    st.plotly_chart(plot_format(fig, 350), width="stretch")
    st.dataframe(cases, hide_index=True, width="stretch")
    st.caption("20 planted corruption cases and 20 independent clean control snapshots. Results are not real-world accuracy or live LLM success.")
    a, b, c = st.columns(3)
    with a:
        st.download_button("↓ Injection cases CSV", cases.to_csv(index=False), "injected_cases.csv", "text/csv", width="stretch")
    with b:
        st.download_button("↓ Clean controls CSV", results["clean_cases"].to_csv(index=False),
                           "clean_controls.csv", "text/csv", width="stretch")
    with c:
        summary = {"injected_corruptions": int(results["corruptions_total"]),
                   "detected_corruptions": int(results["corruptions_detected"]),
                   "injected_case_recall": float(results["recall"]),
                   "clean_snapshot_flag_rate": float(results["clean_snapshot_false_positive_rate"]),
                   "warning": "Synthetic rule evaluation, not a live-model benchmark"}
        st.download_button("↓ Metrics JSON", json.dumps(summary, indent=2), "metrics.json", "application/json", width="stretch")

elif section == "SQL Workspace":
    title_block("05 / VALIDATION OPERATIONS", "SQL Workspace", "Generate rule checks and execute restricted read-only SQL against incoming records.")
    st.markdown("#### Generated pipeline validation checks")
    sql = checks_sql("orders")
    st.code(sql, language="sql")
    st.download_button("↓ Download checks.sql", sql, "checks.sql", "text/plain")
    st.divider()
    st.markdown("#### Local SQL query runner")
    default_query = "SELECT region, COUNT(*) AS orders, ROUND(AVG(amount), 2) AS avg_amount FROM orders GROUP BY region ORDER BY orders DESC"
    query = st.text_area("SELECT query against in-memory `orders` table", value=default_query, height=110)
    if st.button("▶ Execute read-only query", type="primary"):
        try:
            result = run_sql(incoming, query)
            st.dataframe(result, hide_index=True, width="stretch")
            st.caption("Query executes against in-memory SQLite and returns a maximum of 100 rows.")
        except Exception as exc:
            st.error(f"Query rejected: {exc}")

else:  # Reports
    title_block("06 / EXPORT CENTER", "Reports & Evidence", "Download evaluation evidence, rule findings, and investigation outputs for your portfolio.")
    st.markdown("#### Current snapshot findings")
    st.dataframe(pd.DataFrame(findings) if findings else pd.DataFrame(columns=["code", "column", "severity", "detail"]),
                 hide_index=True, width="stretch")
    st.download_button("↓ Download findings.json", json.dumps(findings, indent=2, default=str),
                       "quality_findings.json", "application/json")
    saved = st.session_state.get("run")
    if saved and saved["fingerprint"] == fingerprint:
        st.markdown("#### Latest agent investigation")
        st.download_button("↓ Download Markdown report", saved["output"].get("report", ""),
                           "schemaguard_report.md", "text/markdown")
    else:
        st.info("Run an investigation against the current dataset to make its report available here.")
    st.caption("Privacy: only upload synthetic or non-sensitive datasets to public demonstrations. Hosted apps run on third-party infrastructure.")

st.markdown('<div class="footerline">SCHEMAGUARD AI · LANGGRAPH ORCHESTRATION · SYNTHETIC BENCHMARKS · LOCAL OLLAMA OPTIONAL</div>', unsafe_allow_html=True)
