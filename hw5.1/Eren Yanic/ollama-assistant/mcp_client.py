"""A small Model Context Protocol client for the streamable-HTTP transport.

MCP is JSON-RPC 2.0 over POST. The server replies either with plain JSON or with an
SSE stream, and hands out a session id on the initialize call that every later request
must echo back. That is little enough to implement directly, which keeps the dependency
list at one library and makes the failure modes ours to handle:

  * a cold server answers 503 for a few seconds before it wakes — retry with backoff;
  * an expired session answers 404 — re-initialize once and replay the request;
  * an SSE stream may carry notifications before the result — match on the JSON-RPC id
    rather than trusting the first event to be the answer.
"""

from __future__ import annotations

import json
import threading
import time

import requests

import config

PROTOCOL_VERSION = "2025-06-18"
_RETRY_STATUS = {429, 500, 502, 503, 504}

# Twenty calls half a second apart all succeeded; the same calls back to back drew 503s.
# A conversation never goes faster than this anyway — it only paces bursts, such as
# valuing a portfolio of ten holdings.
_MIN_INTERVAL = 0.5


class MCPError(RuntimeError):
    """Any failure that stops us getting a result out of the MCP server."""


class MCPClient:
    """One session against one MCP server. Connects lazily, on the first tool call."""

    def __init__(self, url: str | None = None, timeout: int | None = None):
        self.url = url or config.BORSA_MCP_URL
        self.timeout = timeout or config.MCP_TIMEOUT
        self._http = requests.Session()
        self._session_id: str | None = None
        self._next_id = 0
        self._last_request = 0.0
        self._lock = threading.Lock()

    # -- plumbing ------------------------------------------------------------
    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
        return headers

    def _post(self, payload: dict, attempts: int = 5) -> requests.Response:
        """POST with backoff over the transient statuses a cold server returns.

        The hosted server sleeps when idle and answers 503 while it wakes, which took
        up to ten seconds when measured — hence exponential waits rather than a fixed one.
        """
        last_error = ""
        for attempt in range(attempts):
            gap = time.time() - self._last_request
            if gap < _MIN_INTERVAL:
                time.sleep(_MIN_INTERVAL - gap)
            self._last_request = time.time()
            try:
                response = self._http.post(
                    self.url, headers=self._headers(), json=payload,
                    timeout=self.timeout, stream=True,
                )
            except requests.RequestException as exc:
                last_error = str(exc)
            else:
                if response.status_code not in _RETRY_STATUS:
                    return response
                last_error = f"HTTP {response.status_code}"
                response.close()
            if attempt < attempts - 1:
                time.sleep(2 * 2 ** attempt)  # 2, 4, 8, 16 s — about half a minute in all
        # A server that restarted has forgotten our session; start clean next time.
        self._session_id = None
        raise MCPError(f"{self.url} is not responding ({last_error}).")

    @staticmethod
    def _read_result(response: requests.Response, want_id: int) -> dict:
        """Pull the JSON-RPC message with the given id out of a JSON or SSE reply."""
        try:
            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
            # text/event-stream carries no charset, and requests then assumes
            # ISO-8859-1 — which turns every Turkish name into mojibake.
            response.encoding = "utf-8"
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                try:
                    message = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if message.get("id") == want_id:  # skip interleaved notifications
                    return message
            raise MCPError("The server closed the stream without answering.")
        finally:
            response.close()

    def _connect(self) -> None:
        self._session_id = None
        response = self._post({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ollama-assistant", "version": "1.0"},
            },
        })
        session_id = response.headers.get("mcp-session-id")
        message = self._read_result(response, 0)
        if "error" in message:
            raise MCPError(f"initialize failed: {message['error'].get('message')}")
        self._session_id = session_id
        # The handshake is only complete once the server has this notification.
        self._http.post(
            self.url, headers=self._headers(),
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            timeout=self.timeout,
        ).close()

    def _rpc(self, method: str, params: dict | None = None, allow_reconnect: bool = True) -> dict:
        with self._lock:
            if self._session_id is None:
                self._connect()
            self._next_id += 1
            request_id = self._next_id
            response = self._post({
                "jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {},
            })
            if response.status_code in (400, 404):
                # The server forgot our session. One clean reconnect, then give up.
                response.close()
                self._session_id = None
                if not allow_reconnect:
                    raise MCPError("The MCP session expired and could not be re-established.")
                reconnect = True
            elif response.status_code >= 400:
                body = response.text[:200]
                response.close()
                raise MCPError(f"MCP error {response.status_code}: {body}")
            else:
                reconnect = False
                message = self._read_result(response, request_id)

        if reconnect:
            return self._rpc(method, params, allow_reconnect=False)
        if "error" in message:
            raise MCPError(message["error"].get("message", "unknown MCP error"))
        return message.get("result", {})

    # -- public API ----------------------------------------------------------
    def list_tools(self) -> list[dict]:
        return self._rpc("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call a remote tool and return its result as text."""
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        chunks = [
            item.get("text", "")
            for item in result.get("content", [])
            if item.get("type") == "text"
        ]
        text = "\n".join(chunk for chunk in chunks if chunk).strip()
        if not text and result.get("structuredContent"):
            text = json.dumps(result["structuredContent"], ensure_ascii=False)
        if result.get("isError"):
            raise MCPError(text or "the tool reported an error")
        return text or "(the server returned no data)"

    def warm(self) -> bool:
        """Shake hands early so the first real question does not pay the wake-up cost."""
        try:
            self._rpc("ping")
        except MCPError:
            return False
        return True

    def close(self) -> None:
        self._http.close()
        self._session_id = None
