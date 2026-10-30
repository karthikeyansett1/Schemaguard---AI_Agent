# Nine-step migration, testing and $20 cap

1. Stop old Streamlit with Ctrl+C. Keep a backup of your current folder.
2. Replace your old `schemaguard-ai` folder with the extracted updated folder (or copy `graph_agent.py`, `app.py`, `requirements.txt`, and `tests/test_graph.py` into the existing folder).
3. `cd schemaguard-ai && source .venv/bin/activate` (create a `.venv` here if missing).
4. `python -m pip install -r requirements.txt` (this installs `langgraph` and `langsmith`).
5. `python -m pytest -q` and inspect any errors.
6. `python -m streamlit run app.py`; test Evaluation lab and the default public-mode graph run.
7. Upload `sample_corrupted.csv` and `sample_reference.csv`. If local upload returns HTTP 403, first clear localhost cookies/use an Incognito tab; don't disable XSRF for public hosting.
8. `ollama list` should show `qwen3:8b`. Toggle Ollama in the investigator, run the question, and inspect tool logs and graph stages. If no tool calls appear, check prompt and model output; don't claim tool usage without evidence.
9. Push **only this folder** to `schemaguard-ai` GitHub repository; deploy in Streamlit Community Cloud (app.py) and add screenshot + URL to README. Do not upload CSVs with sensitive data or .env/API keys.

## Spend cap

- Ollama + Qwen3 8B on Mac: $0 in API fees, local electricity/compute excluded.
- LangGraph / Python packages: $0.
- GitHub public repo: $0.
- Streamlit Community Cloud: target $0 while within free limits.
- LangSmith Developer: free included traces (verify current terms and disable tracing to avoid overages).
- Optional paid cloud LLM: **$0 allocated now**. Keep the $20 unused until there's a demonstrated requirement for public LLM inference; if choosing one later, set provider hard quotas/rate limits before enabling it.

A $20 budget is an upper limit, not an amount you must spend. This project is designed for $0 monthly service charges in default mode.
