# Tool-selection and LangGraph trace demonstration

## Demonstrate Qwen selecting two different tools

1. Launch the app locally with Ollama running (`ollama list` should include `qwen3:8b`).
2. Upload `sample_corrupted.csv` and `sample_reference.csv`, or use built-in demo data.
3. In **AI Investigator**, turn on **Use local Qwen3 8B**.
4. Select **Rule findings / ETL impact** and run. Expand **LLM tool trace**. Confirm that a successful event with `tool: get_quality_findings` appears. Download `agent_trace.json`.
5. Select **Column profiling / nulls** and run. Confirm an event with `tool: get_column_profile`. Download the second `agent_trace.json` and rename it `column_profile_trace.json`.
6. Check that each tool output matches the Data Observability tab. If Qwen chooses the wrong tool, **record that as a failed tool-selection trial**. Do not edit or fabricate the trace. Retry with a clearer prompt and explain the limitation.

The included `tests/test_tool_dispatch.py` uses a *mocked* model to validate that Python executes whichever tool the model requests. It does not measure actual Qwen tool selection.

## Capture portfolio evidence

Run `python scripts/export_benchmark.py`. This writes deterministic benchmark CSV/JSON to `docs/evaluation/`.

For visual evidence, capture screenshots on your Mac: **Observability** showing the corrupted data, **Evaluation lab** showing the benchmark with its caveats, and **AI Investigator** with the expanded tool trace and execution stages. Save screenshots in `docs/screenshots/` and link them in the README. No real screenshot is shipped in this package because the hosted browser has not been run.

Recommended **observability story**: the agent's graph transitions are in `stages`, actual executed tool calls are in `tool_events`, and `model_status` identifies failures and runs that produced an answer without tools.

Do not publish uploads containing personal information. Trace previews can include column names and error descriptions.
