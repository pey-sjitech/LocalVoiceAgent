import re
import httpx
from app import settings, memory, tools
from app.settings import OLLAMA_URL, MODEL, KEEP_ALIVE

conversation_history = memory.load()
_SYSTEM = {"role": "system", "content": settings.SYSTEM_PROMPT.format(
    agent=settings.AGENT_NAME, user=settings.USER_NAME)}
_MAX_TOOL_ROUNDS = 4


def _post(messages: list) -> dict:
    r = httpx.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "tools": tools.SCHEMAS,
              "stream": False, "think": False, "keep_alive": KEEP_ALIVE},
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json()["message"]


def warm() -> None:
    """Load the model into memory so the first real question is fast."""
    try:
        httpx.post(OLLAMA_URL, json={"model": MODEL, "stream": False, "think": False,
                                     "keep_alive": KEEP_ALIVE,
                                     "messages": [{"role": "user", "content": "hi"}],
                                     "options": {"num_predict": 1}}, timeout=300.0)
    except Exception:
        pass


def _clean(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def chat(user_message: str) -> str:
    conversation_history.append({"role": "user", "content": user_message})
    # Tool-call turns live only in this local list; only user/assistant text is persisted.
    messages = [_SYSTEM] + conversation_history
    try:
        for _ in range(_MAX_TOOL_ROUNDS):
            msg = _post(messages)
            calls = msg.get("tool_calls") or []
            if not calls:
                reply = _clean(msg.get("content", "")) or "Done."
                break
            messages.append(msg)
            for c in calls:
                fn = c["function"]
                print(f"  [TOOL] {fn['name']}({fn.get('arguments')})")
                result = tools.call(fn["name"], fn.get("arguments") or {})
                messages.append({"role": "tool", "tool_name": fn["name"], "content": result})
        else:
            reply = "I couldn't finish that request."
        conversation_history.append({"role": "assistant", "content": reply})
        memory.save(conversation_history)
        return reply
    except httpx.ConnectError:
        conversation_history.pop()
        return "Error: Cannot connect to Ollama. Is it running?"
    except Exception as e:
        conversation_history.pop()
        return f"Error: {e}"
