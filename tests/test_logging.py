import asyncio
import logging
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from http.server import ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from unittest.mock import patch

import httpx
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from nmah_military_collection_mcp.logging_config import configure_project_logging
from playground import server as playground

PROJECT = Path(__file__).resolve().parents[1]
TOOL = "search_nmah_military_objects"
TEST_KEY = "logging-test-credential"
TEST_QUERY = "logging-test-private-query"
CLIENT_ID = "1" * 32
INVALID_ID = "untrusted-client-id"

MOCK_SERVER = """
import asyncio
import sys
from pathlib import Path

import httpx

from nmah_military_collection_mcp import server
from nmah_military_collection_mcp.app import create_app

async def respond(request):
    if len(sys.argv) > 1 and request.url.params["start"] == "0":
        gate = Path(sys.argv[1])
        gate.with_suffix(".started").touch()
        while not gate.exists():
            await asyncio.sleep(0.01)
    assert request.headers.get("X-Api-Key")
    if request.url.params["start"] == "1":
        return httpx.Response(429, text="logging-test-private-response")
    return httpx.Response(200, json={
        "status": 200, "responseCode": 1,
        "response": {"rowCount": 0, "rows": []},
    })

server.mcp = create_app(client_factory=lambda: httpx.AsyncClient(
    transport=httpx.MockTransport(respond),
))
server.main()
"""


class LoggingTests(unittest.TestCase):
    def test_project_levels_and_redaction_over_stdio(self):
        for level in ("", "DEBUG", "WARNING"):
            with self.subTest(level=level):
                env = {"LOG_LEVEL": level, "FASTMCP_LOG_LEVEL": "ERROR"}
                with (
                    patch.dict(os.environ, env),
                    tempfile.TemporaryFile(mode="w+") as log,
                ):
                    launch = playground.mcp_client(TEST_KEY).transport
                    self.assertEqual(launch.env["FASTMCP_LOG_LEVEL"], "ERROR")
                    transport = StdioTransport(
                        command=sys.executable,
                        args=["-c", MOCK_SERVER],
                        env=launch.env,
                        cwd=str(PROJECT),
                        keep_alive=False,
                        log_file=log,
                    )
                    asyncio.run(self.check_stdio(transport))
                    log.seek(0)
                    output = log.read()
                self.assertEqual(
                    "INFO nmah_military_collection_mcp.tools" in output,
                    level != "WARNING",
                )
                self.assertEqual(
                    "DEBUG nmah_military_collection_mcp.api_client" in output,
                    level == "DEBUG",
                )
                self.assertIn("WARNING nmah_military_collection_mcp.api_client", output)
                limited_log = next(
                    line for line in output.splitlines() if "status=429" in line
                )
                self.assertRegex(limited_log, r"request_id=[0-9a-f]{32} ")
                self.assertNotIn(f"request_id={INVALID_ID}", output)
                if level != "WARNING":
                    self.assertIn(f"request_id={CLIENT_ID} tool_completed", output)
                for private in (TEST_KEY, TEST_QUERY, "logging-test-private-response"):
                    self.assertFalse(
                        private in output, "Private data appeared in logs."
                    )

    def test_playground_key_check_obeys_project_level(self):
        project_logger = logging.getLogger("nmah_military_collection_mcp")
        success = httpx.Response(
            200, json={"status": 200, "responseCode": 1, "response": {}}
        )
        limited = httpx.Response(429, text="logging-test-private-response")
        for level in ("INFO", "DEBUG", "ERROR"):
            with self.subTest(level=level):
                stream = StringIO()
                with (
                    patch.dict(os.environ, {"LOG_LEVEL": level}),
                    patch.object(project_logger, "handlers", []),
                    patch.object(project_logger, "propagate", project_logger.propagate),
                    patch.object(project_logger, "level", project_logger.level),
                    patch(
                        "playground.server.httpx.get", side_effect=[success, limited]
                    ),
                    redirect_stderr(stream),
                ):
                    configure_project_logging()
                    self.assertIsNone(playground.verify_key(TEST_KEY))
                    self.assertEqual(playground.verify_key(TEST_KEY)[1], 429)
                output = stream.getvalue()
                self.assertEqual(
                    "DEBUG" in output and "status=200" in output, level == "DEBUG"
                )
                self.assertEqual(
                    "WARNING" in output and "status=429" in output, level != "ERROR"
                )
                for private in (TEST_KEY, "logging-test-private-response"):
                    self.assertFalse(
                        private in output, "Private data appeared in logs."
                    )

    def test_concurrent_playground_requests_correlate_out_of_order_over_stdio(self):
        project_logger = logging.getLogger("nmah_military_collection_mcp")
        bridge_log = StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryFile(mode="w+") as mcp_log,
            patch.dict(
                os.environ, {"LOG_LEVEL": "DEBUG", "FASTMCP_LOG_LEVEL": "ERROR"}
            ),
            patch.object(project_logger, "handlers", []),
            patch.object(project_logger, "propagate", project_logger.propagate),
            patch.object(project_logger, "level", project_logger.level),
            patch.object(playground, "DEFAULT_KEY", TEST_KEY),
            patch.object(playground, "key_override", ""),
            redirect_stderr(bridge_log),
            ThreadingHTTPServer(("127.0.0.1", 0), playground.Handler) as server,
        ):
            configure_project_logging()
            gate = Path(directory) / "release"

            def mock_transport(**options):
                options.update(
                    args=["-c", MOCK_SERVER, str(gate)],
                    log_file=mcp_log,
                    keep_alive=False,
                )
                return StdioTransport(**options)

            def search(offset):
                return httpx.post(
                    f"http://127.0.0.1:{server.server_port}/api/search",
                    json={"query": TEST_QUERY, "offset": offset},
                    timeout=15,
                )

            thread = Thread(target=server.serve_forever)
            thread.start()
            try:
                with (
                    patch.object(playground, "StdioTransport", mock_transport),
                    ThreadPoolExecutor(max_workers=2) as pool,
                ):
                    slow = pool.submit(search, 0)
                    try:
                        deadline = monotonic() + 5
                        while not gate.with_suffix(".started").exists():
                            self.assertFalse(slow.done(), "First request ended early.")
                            self.assertLess(
                                monotonic(),
                                deadline,
                                "First request did not reach MCP.",
                            )
                            sleep(0.01)
                        limited = pool.submit(search, 1).result(timeout=10)
                        self.assertFalse(slow.done())
                    finally:
                        gate.touch()
                    success = slow.result(timeout=10)
                    rejected = httpx.post(
                        f"http://127.0.0.1:{server.server_port}/api/search",
                        content=b"invalid json",
                        timeout=5,
                    )
            finally:
                server.shutdown()
                thread.join()

            mcp_log.seek(0)
            mcp_output = mcp_log.read()
        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.json()["total_count"], 0)
        self.assertEqual(limited.status_code, 422)
        self.assertIn("429", limited.json()["error"])
        success_id = success.headers["X-Request-ID"]
        limited_id = limited.headers["X-Request-ID"]
        self.assertNotEqual(success_id, limited_id)
        self.assertEqual(rejected.status_code, 400)
        rejected_id = rejected.headers["X-Request-ID"]
        self.assertRegex(rejected_id, r"^[0-9a-f]{32}$")
        self.assertNotIn(f"request_id={rejected_id}", mcp_output)
        self.assertIn(
            f"request_id={rejected_id} playground_tool_rejected tool={TOOL} status=400",
            bridge_log.getvalue(),
        )
        for request_id, upstream, downstream, offset in (
            (success_id, 200, 200, 0),
            (limited_id, 429, 422, 1),
        ):
            self.assertRegex(request_id, r"^[0-9a-f]{32}$")
            marker = f"request_id={request_id}"
            mcp_lines = [line for line in mcp_output.splitlines() if marker in line]
            self.assertEqual(sum("upstream_response" in line for line in mcp_lines), 1)
            self.assertTrue(any(f"status={upstream}" in line for line in mcp_lines))
            self.assertTrue(any(f"offset={offset}" in line for line in mcp_lines))
            bridge_lines = [
                line for line in bridge_log.getvalue().splitlines() if marker in line
            ]
            self.assertEqual(len(bridge_lines), 1)
            self.assertIn(f"status={downstream}", bridge_lines[0])
        for private in (TEST_KEY, TEST_QUERY, "logging-test-private-response"):
            self.assertFalse(
                private in mcp_output + bridge_log.getvalue(),
                "Private data appeared in logs.",
            )

    async def check_stdio(self, transport):
        async with Client(transport) as client:
            self.assertIn(TOOL, {tool.name for tool in await client.list_tools()})
            success = await client.call_tool(
                TOOL, {"query": TEST_QUERY}, meta={"request_id": CLIENT_ID}
            )
            self.assertEqual(success.structured_content["total_count"], 0)
            limited = await client.call_tool(
                TOOL,
                {"query": TEST_QUERY, "offset": 1},
                raise_on_error=False,
                meta={"request_id": INVALID_ID},
            )
            self.assertTrue(limited.is_error)
            self.assertIn("429", limited.content[0].text)
