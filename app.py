"""SchemaGuard Streamlit demo: public deterministic mode + optional local Ollama."""
import json
from datetime import datetime, timezone
from urllib.request import urlopen

import pandas as pd
import plotly.express as px
import streamlit as st

from ui import initialize
from graph_agent import investigate
from engine import make_clean, scan, profile, evaluate, checks_sql, run_sql

initialize('SchemaGuard AI', 'Data observability • schema drift • anomaly triage • injection benchmark')

@st.cache_data(show_spinner=False)
def benchmark():
    return evaluate()

@st.cache_data(ttl=30, show_spinner=False)
def ollama_ready():
    try:
        with urlopen('http://localhost:11434/api/tags', timeout=0.7) as response:
            return response.status == 200
    except Exception:
        return False

with st.sidebar:
    st.header('Data source')
    uploaded = st.file_uploader('Incoming CSV', type='csv')
    refupload = st.file_uploader('Reference CSV', type='csv')
    source = 'Uploaded CSV' if uploaded else 'Built-in synthetic demo data'
    st.info(f'**Current source:** {source}\n\nDemo data and benchmark cases are synthetic.')
    st.caption('Public hosted mode works without an LLM. Ollama mode needs a model server on the same machine.')

try:
    reference = pd.read_csv(refupload) if refupload else make_clean()
    incoming = pd.read_csv(uploaded) if uploaded else make_clean(seed=55)
    findings = scan(incoming, reference)
except Exception as exc:
    st.error(f'CSV load error: {type(exc).__name__}: {exc}')
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric('Records', f'{len(incoming):,}')
c2.metric('Columns', len(incoming.columns))
c3.metric('Quality flags', len(findings))
c4.metric('Null cells', f'{incoming.isna().sum().sum():,}')

tabs = st.tabs(['Observability', 'Validation SQL', 'Evaluation lab', 'AI Investigator'])
with tabs[0]:
    a, b = st.columns(2)
    p = profile(incoming)
    with a:
        st.subheader('Column health')
        st.dataframe(p, width='stretch', hide_index=True)
    with b:
        st.subheader('Null rate by column')
        if p['missing'].sum() == 0:
            st.success('No missing values in this snapshot.')
        else:
            st.plotly_chart(px.bar(p, x='column', y='missing_pct', title='Missing values (%)'), width='stretch')
    st.subheader('Quality findings')
    if findings:
        st.dataframe(pd.DataFrame(findings), width='stretch', hide_index=True)
    else:
        st.success('No violations under configured rules. This does not prove the data is perfectly clean.')

with tabs[1]:
    sql = checks_sql()
    st.code(sql, language='sql')
    st.download_button('Download checks.sql', sql, file_name='checks.sql')
    st.subheader('Read-only local SQL workspace')
    query = st.text_area('Query incoming dataset', 'SELECT region, COUNT(*) AS orders, ROUND(AVG(amount),2) AS avg_amount FROM orders GROUP BY region ORDER BY orders DESC')
    if st.button('Execute SELECT'):
        try:
            st.dataframe(run_sql(incoming, query), hide_index=True, width='stretch')
        except Exception as exc:
            st.error(str(exc))

with tabs[2]:
    scores = benchmark()
    a, b, c = st.columns(3)
    a.metric('Corruptions detected', f'{scores["corruptions_detected"]}/20')
    b.metric('Injected-case recall', f'{scores["recall"]:.0%}')
    c.metric('Clean-snapshot flag rate', f'{scores["clean_snapshot_false_positive_rate"]:.0%}')
    st.dataframe(scores['cases'], width='stretch', hide_index=True)
    st.plotly_chart(px.histogram(scores['cases'], x='truth', color='detected', barmode='group',
                                 title='Detection by corruption family'), width='stretch')
    st.caption('Synthetic injected-case recall and clean-snapshot flag rate; not live-model accuracy or real-world precision.')
    st.download_button('Download benchmark cases.csv', scores['cases'].to_csv(index=False),
                       file_name='benchmark_cases.csv', mime='text/csv')
    st.download_button('Download clean control cases.csv', scores['clean_cases'].to_csv(index=False),
                       file_name='clean_control_cases.csv', mime='text/csv')
    metrics = {'corruptions_detected': scores['corruptions_detected'],
               'corruptions_total': scores['corruptions_total'], 'recall': scores['recall'],
               'clean_snapshot_false_positive_rate': scores['clean_snapshot_false_positive_rate'],
               'benchmark_type': 'synthetic_rules_only'}
    st.download_button('Download evaluation metrics.json', json.dumps(metrics, indent=2),
                       file_name='evaluation_metrics.json', mime='application/json')

with tabs[3]:
    st.subheader('LangGraph AI Investigator')
    available = ollama_ready()
    st.caption('Deterministic LangGraph workflow works publicly; model-directed tools require local Qwen3 8B.')
    if not available:
        st.info('Local Ollama endpoint not detected. Deterministic mode remains fully usable.')
    llm = st.toggle('Use local Qwen3 8B (Ollama)', value=False, disabled=not available)
    examples = {
        'Rule findings / ETL impact': 'Call get_quality_findings. Identify confirmed violations, the exact count and downstream ETL risk.',
        'Column profiling / nulls': 'Call get_column_profile. Which columns have null values and what are their data types and unique counts?',
        'Synthetic evaluation': 'Call get_baseline_evaluation. Report injected-case recall and clean snapshot false-positive rate with caveats.',
    }
    choice = st.selectbox('Tool-selection demonstration', list(examples))
    question = st.text_area('Investigation question', value=examples[choice], key=choice)
    if st.button('Run LangGraph investigation', type='primary', width='stretch'):
        with st.spinner('Inspecting evidence and executing workflow...'):
            try:
                st.session_state['last_investigation'] = investigate(incoming, reference, question, llm_enabled=llm)
                st.session_state['last_question'] = question
                st.session_state['last_source'] = source
            except Exception as exc:
                st.error(f'Investigation failed: {type(exc).__name__}: {exc}')
    if 'last_investigation' in st.session_state:
        result = st.session_state['last_investigation']
        status = result.get('model_status', 'unknown')
        if status == 'failed':
            st.error('Ollama execution failed; see report. This is not a successful LLM run.')
        elif status == 'completed':
            st.success('Qwen investigation completed. Verify the actual tool trace below.')
        else:
            st.info(f'Execution mode / status: {status}')
        st.markdown(result['report'])
        st.download_button('Download investigation report', result['report'], file_name='schemaguard_report.md')
        with st.expander('LangGraph execution stages', expanded=True):
            st.dataframe(pd.DataFrame(result['stages']), width='stretch', hide_index=True)
        with st.expander('LLM tool trace', expanded=True):
            trace = result.get('tool_events', [])
            st.json(trace)
            st.caption('These are actual tool events. An empty list means no successful tool calls.')
        with st.expander('Generated SQL checks'):
            st.code(result['sql'], language='sql')
            st.caption(f'SQL template shape validated: {result.get("sql_validated", False)}. Not executed.')
        payload = {'captured_at_utc': datetime.now(timezone.utc).isoformat(),
                   'question': st.session_state.get('last_question'),
                   'data_source': st.session_state.get('last_source'),
                   'model': 'qwen3:8b' if result.get('model_status') not in ('disabled', 'not_requested') else None,
                   'model_status': status, 'stages': result['stages'],
                   'tool_events': result.get('tool_events', []),
                   'rule_findings': result['findings'],
                   'sql_template_validated': result.get('sql_validated', False),
                   'notes': 'Aggregated trace; verify counts against snapshot before publishing.'}
        st.download_button('Download reproducible trace.json', json.dumps(payload, indent=2, default=str),
                           file_name='agent_trace.json', mime='application/json')
