import datetime
import glob
import json
import os
import time


def _tail(path, size=262144):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        length = f.tell()
        start = max(0, length - size)
        f.seek(start)
        data = f.read().decode("utf-8", errors="replace")
    if start > 0:
        newline = data.find("\n")
        if newline != -1:
            data = data[newline + 1 :]
    return data


def _clean(text, limit=80):
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: max(0, limit - 1)] + "…"
    return text


def _extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                t = item.get("text", "")
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    return ""


def _find_cc_session():
    root = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
    files = [f for f in files if "subagent" not in f]
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _find_codex_session():
    root = os.path.join(os.path.expanduser("~"), ".codex", "sessions")
    files = glob.glob(os.path.join(root, "**", "rollout-*.jsonl"), recursive=True)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _parse_cc(path):
    mtime = os.path.getmtime(path)
    active = (time.time() - mtime) < 30
    task = None
    model = None
    try:
        for line in _tail(path).splitlines():
            obj = json.loads(line)
            otype = obj.get("type")
            if otype in ("human", "user"):
                msg = obj.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else ""
                text = _extract_text(content)
                if text and "<system-reminder>" not in text:
                    task = _clean(text)
            if otype == "assistant":
                m = obj.get("model") or obj.get("message", {}).get("model")
                if m:
                    model = str(m)
    except Exception:
        pass
    return {
        "active": active,
        "task": task,
        "model": model,
        "progress": None,
        "elapsed": None,
        "tokens": None,
        "last_finished": None,
        "source": "cc",
        "mtime": mtime,
    }


def _user_text_codex(payload):
    if payload.get("type") == "user_message":
        text = payload.get("message")
        if isinstance(text, str):
            return text
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return _extract_text(content)
    return ""


def _parse_codex(path):
    mtime = os.path.getmtime(path)
    task = None
    model = None
    progress = None
    started_at = None
    total_tokens = None
    last_finished = None
    try:
        for line in _tail(path).splitlines():
            obj = json.loads(line)
            payload = obj.get("payload", {})
            ptype = payload.get("type")
            if ptype == "task_started":
                started = payload.get("started_at")
                if isinstance(started, (int, float)):
                    started_at = float(started)
            elif ptype == "token_count":
                info = payload.get("info") or {}
                usage = info.get("total_token_usage") or {}
                tokens = usage.get("total_tokens")
                if isinstance(tokens, (int, float)):
                    total_tokens = int(tokens)
            elif ptype == "task_complete":
                completed = payload.get("completed_at")
                if isinstance(completed, (int, float)):
                    last_finished = float(completed)
            if ptype in ("user_message", "message") and payload.get("role") in (
                None,
                "user",
            ):
                text = _user_text_codex(payload)
                if (
                    text
                    and "<environment_context>" not in text
                    and "permissions instructions" not in text
                ):
                    marker = "My request for Codex:"
                    if marker in text:
                        text = text.split(marker, 1)[1]
                    task = _clean(text)
            if ptype == "agent_message" and payload.get("phase") == "commentary":
                message = payload.get("message")
                if isinstance(message, str) and message.strip():
                    progress = _clean(message)
            elif ptype == "task_complete":
                message = payload.get("last_agent_message")
                if isinstance(message, str) and message.strip():
                    progress = _clean(message)
            thread_settings = payload.get("thread_settings")
            if isinstance(thread_settings, dict) and thread_settings.get("model"):
                model = str(thread_settings["model"])
            elif payload.get("model"):
                model = str(payload["model"])
    except Exception:
        pass
    active = (time.time() - mtime) < 8
    return {
        "active": active,
        "task": task,
        "model": model,
        "progress": progress,
        "elapsed": (
            int(time.time() - started_at)
            if active and started_at is not None
            else None
        ),
        "tokens": total_tokens,
        "last_finished": (
            datetime.datetime.fromtimestamp(last_finished).strftime("%H:%M")
            if last_finished is not None
            else None
        ),
        "source": "codex",
        "mtime": mtime,
    }


def get_codex_status():
    empty = {
        "active": False,
        "task": None,
        "model": None,
        "progress": None,
        "elapsed": None,
        "tokens": None,
        "last_finished": None,
    }
    cc_path = _find_cc_session()
    codex_path = _find_codex_session()

    results = []
    if cc_path:
        results.append(_parse_cc(cc_path))
    if codex_path:
        results.append(_parse_codex(codex_path))

    if not results:
        return empty

    active = [r for r in results if r["active"]]
    if active:
        best = max(active, key=lambda r: r["mtime"])
    else:
        best = max(results, key=lambda r: r["mtime"])

    best.pop("source", None)
    best.pop("mtime", None)
    return best
