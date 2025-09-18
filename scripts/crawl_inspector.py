#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch crawl MCP servers' tools via @modelcontextprotocol/inspector.

Input sources:
- Website/mcpso_servers_cleaned.json (preferred)
- Fallback: Crawler/Servers/mcpso_servers.json (if cleaned not found)

Output:
- data/tools.json (list of {server_name, url, transport, tools, status, error})

Environment variables:
- CRAWL_LIMIT: optional int limit of servers to try (default: 100)
- CRAWL_TIMEOUT_SEC: per call timeout seconds (default: 45)

Notes:
- Prefer server_config when available (it is already an MCP client config snippet)
- Else prefer sse_url; generate a minimal config for SSE
- Else fallback to server_command; wrap in bash -lc to execute
"""

import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_servers_dataset(repo_root: Path) -> List[Dict[str, Any]]:
    candidates = [
        repo_root / "Website" / "mcpso_servers_cleaned.json",
        repo_root / "Crawler" / "Servers" / "mcpso_servers.json",
    ]
    for path in candidates:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                except Exception as e:
                    print(f"Failed to load {path}: {e}")
    return []


def parse_server_config(config_str: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """Parse server_config JSON string and return (config_obj, first_server_name)."""
    try:
        cfg = json.loads(config_str)
        mcp_servers = cfg.get("mcpServers") or cfg.get("mcpservers")
        if isinstance(mcp_servers, dict) and len(mcp_servers) > 0:
            server_name = next(iter(mcp_servers.keys()))
            return cfg, server_name
    except Exception:
        return None
    return None


def build_config_for_sse(url: str, name_hint: str = "server") -> Tuple[Dict[str, Any], str, str]:
    name = f"{name_hint}-sse" if name_hint else "server-sse"
    cfg = {"mcpServers": {name: {"url": url}}}
    return cfg, name, "sse"


def build_config_for_command(command_str: str, name_hint: str = "server") -> Tuple[Dict[str, Any], str, str]:
    name = f"{name_hint}-stdio" if name_hint else "server-stdio"
    # Wrap entire command in bash -lc so inline env vars are honored
    cfg = {"mcpServers": {name: {"command": "bash", "args": ["-lc", command_str]}}}
    return cfg, name, "stdio"


def call_inspector_with_config(config_obj: Dict[str, Any], server_name: str, timeout_sec: int) -> Tuple[str, str, int]:
    """Run inspector and return (stdout, stderr, returncode)."""
    tmp_file = None
    try:
        tmp = tempfile.NamedTemporaryFile(prefix="inspector_cfg_", suffix=".json", delete=False)
        tmp_file = tmp.name
        tmp.write(json.dumps(config_obj, ensure_ascii=False, indent=2).encode("utf-8"))
        tmp.flush()
        tmp.close()

        cmd = [
            "npx",
            "-y",
            "@modelcontextprotocol/inspector",
            "--config",
            tmp_file,
            "--server",
            server_name,
            "--cli",
            "--method",
            "tools/list",
        ]

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
        )
        return proc.stdout, proc.stderr, proc.returncode
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.unlink(tmp_file)
            except Exception:
                pass


def try_parse_json_from_output(output: str) -> Optional[Dict[str, Any]]:
    output = output.strip()
    if not output:
        return None
    # Fast path
    try:
        return json.loads(output)
    except Exception:
        pass
    # Heuristic: extract first JSON object-like span
    start = output.find("{")
    end = output.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            candidate = output[start : end + 1]
            return json.loads(candidate)
        except Exception:
            return None
    return None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "tools.json"

    servers = load_servers_dataset(repo_root)
    if not servers:
        print("No servers dataset found. Abort.")
        return 1

    crawl_limit = int(os.environ.get("CRAWL_LIMIT", "100"))
    timeout_sec = int(os.environ.get("CRAWL_TIMEOUT_SEC", "45"))

    results: List[Dict[str, Any]] = []
    attempted = 0
    total = len(servers)
    print(f"Loaded {total} server entries. Limit: {crawl_limit}")

    for idx, item in enumerate(servers):
        if attempted >= crawl_limit:
            break

        name = item.get("name") or item.get("title") or f"server-{idx+1}"
        url = item.get("url")
        sse_url = item.get("sse_url")
        server_command = item.get("server_command")
        server_config_str = item.get("server_config")

        config_obj: Optional[Dict[str, Any]] = None
        server_name: Optional[str] = None
        transport: Optional[str] = None
        source: Optional[str] = None

        # Priority: explicit server_config > sse_url > server_command
        if isinstance(server_config_str, str) and server_config_str.strip():
            parsed = parse_server_config(server_config_str)
            if parsed:
                config_obj, server_name = parsed
                # Infer transport by presence of url/command
                try:
                    conf = config_obj.get("mcpServers", {}).get(server_name, {})
                except Exception:
                    conf = {}
                if "url" in conf:
                    transport = "sse"
                elif "command" in conf:
                    transport = "stdio"
                source = "server_config"
        if not config_obj and isinstance(sse_url, str) and sse_url.strip():
            config_obj, server_name, transport = build_config_for_sse(sse_url, name)
            source = "sse_url"
        if not config_obj and isinstance(server_command, str) and server_command.strip():
            config_obj, server_name, transport = build_config_for_command(server_command, name)
            source = "server_command"

        if not config_obj or not server_name:
            # Nothing to do for this entry
            continue

        attempted += 1
        print(f"[{attempted}] {name} via {transport} ({source}) ...", flush=True)

        stdout, stderr, rc = call_inspector_with_config(config_obj, server_name, timeout_sec)
        resp_json = try_parse_json_from_output(stdout)

        status = "ok" if (rc == 0 and isinstance(resp_json, dict)) else "error"
        tools = []
        error_message = None
        if status == "ok":
            tools = resp_json.get("tools") or []
            if not isinstance(tools, list):
                tools = []
        else:
            # capture concise error
            err_snippet = (stderr or "").strip()
            if not err_snippet:
                err_snippet = (stdout or "").strip()
            error_message = err_snippet[:500]

        results.append(
            {
                "server_name": name,
                "repo_url": url,
                "transport": transport,
                "source": source,
                "tools": tools,
                "status": status,
                "error": error_message,
            }
        )

    # Write output
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(results)} results to {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

