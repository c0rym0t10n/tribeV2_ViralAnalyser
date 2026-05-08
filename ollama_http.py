"""HTTP transport + structured-JSON parsing for the local Ollama server.

Lifted out of :mod:`ollama_runtime` in Stage-2 / G4. Owns:

* The base URL / timeout constants (``OLLAMA_BASE_URL``, ``OLLAMA_TIMEOUT_SECONDS``).
* :func:`request_json` — POST/GET to the Ollama HTTP API with stdlib
  ``urllib`` (no extra deps).
* :func:`rewrite_with_ollama` — the structured-output retry loop used when
  asking the LLM for a JSON-shaped reply (``num_predict`` sweep, content
  extraction, ``_parse_json_object`` salvage).
* :func:`parse_json_object` — best-effort recovery of a single JSON object
  from a possibly-noisy LLM string output.

Keeps the runtime module focused on prompt building and the simplified-review
flow, and gives any future caller (e.g. translation, summarisation) a stable
import target.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


OLLAMA_BASE_URL = "http://localhost:11434/api"
OLLAMA_TIMEOUT_SECONDS = 90


def request_json(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST a JSON payload (or GET if ``payload`` is ``None``) to ``path`` on
    the local Ollama API and decode the response as a dict. Returns ``{}`` if
    the response decodes to anything other than a dict — callers always treat
    the result as a dict and look up keys defensively."""
    body = None
    headers: dict[str, str] = {}
    method = "GET"
    if payload is not None:
        method = "POST"
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(f"{OLLAMA_BASE_URL}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
        raw = response.read().decode("utf-8")
    loaded = json.loads(raw)
    return loaded if isinstance(loaded, dict) else {}


def rewrite_with_ollama(
    model: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    num_predict_values: tuple[int, ...] = (900, 1400),
) -> dict[str, Any] | None:
    """Ask Ollama's ``/chat`` endpoint for a structured JSON reply, sweeping
    ``num_predict`` values until one returns parseable content. Returns the
    parsed dict on success, or ``None`` if every attempt failed (network
    error, no content, or unparseable JSON)."""
    for num_predict in num_predict_values:
        try:
            response = request_json(
                "/chat",
                {
                    "model": model,
                    "stream": False,
                    "think": False,
                    "format": schema,
                    "messages": messages,
                    "options": {"temperature": 0.2, "num_predict": num_predict},
                    "keep_alive": "15m",
                },
            )
        except (OSError, URLError, json.JSONDecodeError):
            continue

        message = response.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        parsed = parse_json_object(content)
        if isinstance(parsed, dict):
            return parsed
    return None


def parse_json_object(content: str) -> dict[str, Any] | None:
    """Best-effort recovery of a single JSON object from a noisy string.

    First tries a strict ``json.loads`` of the whole input. If that fails,
    walks the string from the first ``{`` and tracks brace depth (respecting
    string literals + escapes) to extract a candidate object substring, which
    is then loaded. Returns ``None`` if no parseable object is found.
    """
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = content.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(content[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = content[start : index + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None
