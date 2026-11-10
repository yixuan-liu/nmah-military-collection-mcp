import copy
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastmcp import Client

from nmah_military_collection_mcp.app import create_app

METADATA_TOOL = "get_nmah_military_object_metadata"


class ToolContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_sends_scope_and_returns_unmodified_rows(self):
        requests = []
        clients = []
        row = {"id": "example", "content": {"unmodeled_field": [1, 2]}}

        def respond(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "status": 200,
                    "responseCode": 1,
                    "response": {"rows": [row], "rowCount": 9},
                },
            )

        def make_client():
            client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
            clients.append(client)
            return client

        with patch.dict(os.environ, {"SMITHSONIAN_API_KEY": "offline-test-key"}):
            async with Client(create_app(client_factory=make_client)) as client:
                for has_images in (False, True):
                    page = (
                        await client.call_tool(
                            "search_nmah_military_objects",
                            {
                                "query": "  ",
                                "rows": 1,
                                "offset": 2,
                                "has_images": has_images,
                            },
                        )
                    ).data
                    self.assertEqual(page["objects"], [row])
                    self.assertEqual(page["next_offset"], 3)
                    self.assertEqual(page["total_count"], 9)
                    self.assertIs(page["has_images"], has_images)
                    request = requests[-1]
                    self.assertEqual(request.url.params["q"], "*")
                    self.assertEqual(request.url.params["start"], "2")
                    filters = [
                        "unit_code:NMAH",
                        "type:edanmdm",
                        r"set_name:Military\ and\ Society\:\ Armed\ Forces\ History*",
                    ]
                    if has_images:
                        filters.append("online_media_type:Images")
                    self.assertEqual(json.loads(request.url.params["fqs"]), filters)
                    self.assertEqual(request.headers["X-Api-Key"], "offline-test-key")
                    self.assertNotIn("api_key", request.url.params)
        self.assertEqual(len(clients), 1)
        self.assertTrue(clients[0].is_closed)

    async def test_metadata_scope_and_upstream_failures(self) -> None:
        """Replay a real record and exercise identity, scope, and upstream failures."""
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/nmah_463569-content.json").read_text()
        )
        current = fixture
        status = 200
        timeout = False
        calls = []

        def respond(request):
            url = str(request.url)
            calls.append(url)
            assert url.endswith("/content/edanmdm%3Anmah_463569")
            assert (
                "api_key" not in url
                and request.headers["X-Api-Key"] == "offline-test-key"
            )
            if timeout:
                raise httpx.ReadTimeout("Simulated timeout", request=request)
            return httpx.Response(status, request=request, json=current)

        app = create_app(
            client_factory=lambda: httpx.AsyncClient(
                transport=httpx.MockTransport(respond)
            )
        )
        with patch.dict(os.environ, {"SMITHSONIAN_API_KEY": "offline-test-key"}):
            async with Client(app) as client:
                result = await client.call_tool(
                    METADATA_TOOL, {"record_id": "nmah_463569"}
                )
                assert result.data == fixture["response"]
                for invalid in [
                    "",
                    "nmah_463569/../stats",
                    "edanmdm:nmah_463569",
                    "nmnh_1",
                    "nmah_1\n",
                ]:
                    count = len(calls)
                    result = await client.call_tool(
                        METADATA_TOOL, {"record_id": invalid}, raise_on_error=False
                    )
                    assert result.is_error and len(calls) == count
                variants = []
                for path, value in [
                    (("unitCode",), "NMNH"),
                    (("content", "descriptiveNonRepeating", "unit_code"), "NMNH"),
                    (("content", "descriptiveNonRepeating", "record_ID"), "nmah_1"),
                    (
                        ("content", "freetext", "setName"),
                        [{"content": "Domestic Life"}],
                    ),
                    (("content", "freetext", "setName"), []),
                    (("type",), "ead_collection"),
                ]:
                    altered = copy.deepcopy(fixture)
                    target = altered["response"]
                    for part in path[:-1]:
                        target = target[part]
                    target[path[-1]] = value
                    variants.append(altered)
                variants.extend(
                    [
                        {},
                        {"status": 200, "responseCode": 1, "response": []},
                        {"status": 200, "responseCode": 0},
                    ]
                )
                for current in variants:
                    result = await client.call_tool(
                        METADATA_TOOL,
                        {"record_id": "nmah_463569"},
                        raise_on_error=False,
                    )
                    assert result.is_error
                current = fixture
                for status in [404, 429, 500]:
                    result = await client.call_tool(
                        METADATA_TOOL,
                        {"record_id": "nmah_463569"},
                        raise_on_error=False,
                    )
                    assert result.is_error
                status = 200
                timeout = True
                result = await client.call_tool(
                    METADATA_TOOL, {"record_id": "nmah_463569"}, raise_on_error=False
                )
                assert result.is_error
