import streamlit as st

def initialize(title, subtitle, accent="#14b8a6"):
    st.set_page_config(page_title=title, page_icon="◈", layout="wide")
    st.markdown(f'''<style>
        .stApp {{background: #0b1220; color: #e2e8f0;}}
        [data-testid="stMetric"] {{background:#111f33;border:1px solid #26364e;border-radius:12px;padding:12px;}}
        div.stButton>button {{border-radius:10px;}}
        h1,h2,h3 {{letter-spacing:-.035em;}}
        .kicker {{font-size:12px;font-weight:800;letter-spacing:.16em;color:{accent};}}
        .hero {{border:1px solid #26364e;border-radius:16px;padding:20px 24px;
        background:linear-gradient(110deg,#16243a,#0b1220);margin-bottom:20px;}}
    </style>''', unsafe_allow_html=True)
    st.markdown(f'<div class="hero"><div class="kicker">LOCAL INTELLIGENCE / PORTFOLIO LAB</div><h1 style="margin:.3em 0">{title}</h1><div style="color:#94a3b8">{subtitle}</div></div>',unsafe_allow_html=True)

def agent_panel(tools, starter, model="qwen3:8b"):
    from agent import ask_agent
    st.subheader("Ask the investigator — local Ollama mode")
    st.caption("The hosted demo works without a model. Optional AI investigations require Ollama on your own computer; hosted Streamlit cannot reach your local Ollama server.")
    question = st.text_area("Your question", starter, key="question")
    if st.button("Run agent investigation", type="primary", use_container_width=True):
        with st.spinner("Ollama is selecting tools..."):
            try:
                answer, trace = ask_agent(question, tools, model=model)
                st.markdown(answer)
                with st.expander("Tool-call trace", expanded=True): st.json(trace)
            except Exception as e:
                st.error(f"Cannot reach local Ollama: {e}. Run `ollama serve` and `ollama pull {model}`.")
