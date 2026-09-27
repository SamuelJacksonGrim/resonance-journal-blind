"""MCP server over stdio (newline-delimited JSON-RPC 2.0), standard library only.

Exposes read tools and additive writes. `forget` and `unrelate` are deliberately
absent: removing the operator's memory is a CLI action (Contracts guardrail).
"""

from __future__ import annotations

import json
import sys
from typing import IO

from . import __version__
from .memory import NotFound, Resonance, ValidationError
from .weights import RELATION_TYPES

PROTOCOL_VERSION = "2025-06-18"
MAX_LINE_BYTES = 1_000_000

_DATE = {"type": "string", "description": "ISO-8601 date or datetime"}

TOOLS = [
    {
        "name": "context",
        "description": ("Best first call. Returns a compact, prompt-ready block of the stored notes "
                        "most relevant to the query, found by following weighted word relationships, "
                        "never longer than budget_chars."),
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string"},
            "budget_chars": {"type": "integer", "minimum": 200, "maximum": 100000, "default": 4000},
            "since": _DATE, "until": _DATE}, "required": ["query"]},
    },
    {
        "name": "recall",
        "description": ("Structured recall: ranked related terms (with the path of weighted links that "
                        "reached each) and ranked notes with the terms that matched them."),
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
            "hops": {"type": "integer", "minimum": 0, "maximum": 4, "default": 2},
            "since": _DATE, "until": _DATE}, "required": ["query"]},
    },
    {
        "name": "neighbors",
        "description": "The weighted relationships of one word, strongest first, with their evidence.",
        "inputSchema": {"type": "object", "properties": {
            "term": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20}},
            "required": ["term"]},
    },
    {
        "name": "remember",
        "description": ("Store a note. Word relationships are learned from it automatically. "
                        "Storing identical text twice is a no-op."),
        "inputSchema": {"type": "object", "properties": {
            "text": {"type": "string"},
            "source": {"type": "string"},
            "importance": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5}},
            "required": ["text"]},
    },
    {
        "name": "relate",
        "description": ("Assert a typed relationship between two single words. Overrides the learned "
                        "weight for that pair; weight 0 suppresses a spurious learned link."),
        "inputSchema": {"type": "object", "properties": {
            "a": {"type": "string"}, "b": {"type": "string"},
            "type": {"type": "string", "enum": list(RELATION_TYPES)},
            "weight": {"type": "number", "minimum": 0, "maximum": 1, "default": 1.0}},
            "required": ["a", "b", "type"]},
    },
    {
        "name": "stats",
        "description": "Store sizes and bounds.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

_ALLOWED_ARGS = {t["name"]: set(t["inputSchema"]["properties"]) for t in TOOLS}


def call_tool(mem: Resonance, name: str, args: dict) -> dict:
    if name not in _ALLOWED_ARGS:
        raise ValidationError(f"unknown tool {name!r}")
    if not isinstance(args, dict):
        raise ValidationError("arguments must be an object")
    extra = set(args) - _ALLOWED_ARGS[name]
    if extra:
        raise ValidationError(f"unexpected arguments: {', '.join(sorted(extra))}")
    if name == "context":
        return {"content": [{"type": "text", "text": mem.context(**args)}]}
    fn = {"recall": mem.recall, "neighbors": mem.neighbors, "remember": mem.remember,
          "relate": mem.relate, "stats": mem.stats}[name]
    return {"content": [{"type": "text", "text": json.dumps(fn(**args), ensure_ascii=False)}]}


def handle(mem: Resonance, msg) -> dict | None:
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid request")
    mid, method, params = msg.get("id"), msg["method"], msg.get("params") or {}
    is_notification = "id" not in msg
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION)
                  if isinstance(params, dict) else PROTOCOL_VERSION,
                  "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "resonance", "version": __version__}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        if not isinstance(params, dict):
            return _error(mid, -32602, "params must be an object")
        try:
            result = call_tool(mem, params.get("name"), params.get("arguments") or {})
        except TypeError:
            result = _tool_error("invalid arguments")
        except (ValidationError, NotFound) as e:
            result = _tool_error(str(e))
    elif method.startswith("notifications/"):
        return None
    else:
        return None if is_notification else _error(mid, -32601, f"method not found: {method}")
    return None if is_notification else {"jsonrpc": "2.0", "id": mid, "result": result}


def _tool_error(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve(mem: Resonance, stdin: IO[str], stdout: IO[str]) -> None:
    for line in stdin:
        if not line.strip():
            continue
        if len(line) > MAX_LINE_BYTES:
            reply = _error(None, -32600, "message too large")
        else:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                reply = _error(None, -32700, "parse error")
            else:
                try:
                    reply = handle(mem, msg)
                except Exception:  # keep serving; never echo note text
                    reply = _error(msg.get("id") if isinstance(msg, dict) else None,
                                   -32603, "internal error")
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="resonance-mcp", description="Resonance MCP server (stdio).")
    p.add_argument("--db", default=None)
    args = p.parse_args(argv)
    with Resonance(args.db) as mem:
        serve(mem, sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
