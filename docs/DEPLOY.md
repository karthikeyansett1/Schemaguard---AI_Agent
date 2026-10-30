# Deploy free public SchemaGuard demo

## Important distinction

Streamlit Community Cloud hosts the *Python analytics UI*, **not** Qwen3 8B. Visitors can use profiling, upload their own CSV, run synthetic benchmark evaluations, generate validation templates, and run the deterministic LangGraph path. The Ollama toggle is disabled automatically when the local Ollama endpoint is unavailable.

## Step-by-step

1. In Terminal from this project directory: `python -m pytest -q` and `python scripts/export_benchmark.py`.
2. Initialize/push the repository to your own public GitHub `schemaguard-ai` repository:

   ```bash
   git init
   git add .
   git commit -m "SchemaGuard: LangGraph triage and benchmark"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/schemaguard-ai.git
   git push -u origin main
   ```

3. Visit https://share.streamlit.io/ and sign in with GitHub.
4. Choose **Create app** → **I have an app**, select repository `schemaguard-ai`, branch `main`, entry point `app.py`.
5. Select Python **3.12** in Advanced settings if prompted. No API key or secrets needed.
6. Click **Deploy** and wait for a working URL. Record the actual URL in the README; do not invent one.
7. Open the public link in an incognito/private window. Check that *all four tabs* work, the evaluator runs, CSV uploads work, and **the Ollama toggle is disabled**. If uploads fail with a 403, investigate session/cookie/proxy logs; do **not** disable XSRF protections on the public server.
8. Add the URL and local demo screenshots to your GitHub README.

## Local LLM mode

On your Mac:

```bash
ollama pull qwen3:8b
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The Ollama application must be running. Choose the LLM toggle in **AI Investigator** and inspect exported `agent_trace.json` for actual executed calls. Closing the app window does not always terminate Ollama's background server.

## No unexpected API charges

No provider API key is included. The public UI only needs Streamlit's free Community Cloud resources (subject to its current usage limits); local Qwen inference is performed on the user's own machine. A public **LLM-powered** endpoint would require additional separately configured compute/inference and safeguards.
