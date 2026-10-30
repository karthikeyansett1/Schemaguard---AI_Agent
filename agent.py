"""Tool-calling agent with deterministic tool execution; Ollama is optional for analysis."""
import json
from typing import Callable

def ask_agent(question: str, tools: list[Callable], model: str = "qwen3:8b", max_rounds: int = 5):
    """Returns (answer, trace). No arbitrary Python or shell execution permitted."""
    from ollama import chat
    registry = {f.__name__: f for f in tools}
    messages = [
        {"role": "system", "content": (
            "You are a careful analytics investigator. Use tools to collect numerical evidence before conclusions. "
            "Never invent results. Distinguish flags from confirmed causality, significance from practical importance. "
            "If a tool errors, acknowledge it. Do not claim fraud or positive treatment impact without evidence. "
            "Respond concisely with actual numbers and limitations.")},
        {"role": "user", "content": question},
    ]
    trace = []
    for _ in range(max_rounds):
        response = chat(model=model, messages=messages, tools=tools, options={"temperature": 0})
        msg = response.message
        messages.append(msg.model_dump(exclude_none=True) if hasattr(msg, "model_dump") else dict(msg))
        calls = msg.tool_calls or []
        if not calls:
            return (msg.content or "The model returned no text."), trace
        for call in calls:
            name = call.function.name
            args = call.function.arguments or {}
            if isinstance(args, str):
                try: args = json.loads(args)
                except json.JSONDecodeError: args = {}
            if name not in registry:
                result = {"error": f"Unknown tool {name}"}
            else:
                try: result = registry[name](**args)
                except Exception as e: result = {"error": str(e)}
            output = result if isinstance(result, str) else json.dumps(result, default=str)
            trace.append({"tool": name, "arguments": args, "result": output[:2500]})
            messages.append({"role": "tool", "tool_name": name, "content": output[:12000]})
    return "Stopped after reaching the tool-call limit. Review the tool trace.", trace
