import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastmcp import Client

from nmah_military_collection_mcp.app import create_app

TOOL = "get_nmah_military_object_image_assets"
RECORD_ID = "nmah_463569"
IDS = "https://ids.si.edu"
MANIFEST_URL = f"{IDS}/ids/manifest/edanmdm:{RECORD_ID}"


def image_url(media_id):
    return f"{IDS}/ids/iiif/{media_id}/full/full/0/default.jpg"


def manifest_image(media_id):
    return {
        "resource": {
            "@id": image_url(media_id),
            "format": "image/jpeg",
            "width": 428,
            "height": 640,
        }
    }


class ImageAssetToolTests(unittest.IsolatedAsyncioTestCase):
    async def call(self, *, media=None, images=(), manifest_status=200, in_scope=True):
        content = json.loads(
            (Path(__file__).parent / "fixtures/nmah_463569-content.json").read_text()
        )
        record = content["response"]["content"]
        if media is not None:
            record["descriptiveNonRepeating"]["online_media"] = {"media": media}
        if not in_scope:
            record["freetext"]["setName"] = [{"content": "Domestic Life"}]

        calls = []

        def respond(request):
            calls.append(request)
            if request.url.host == "api.si.edu":
                self.assertEqual(request.headers["X-Api-Key"], "offline-test-key")
                return httpx.Response(200, json=content)
            self.assertEqual(str(request.url), MANIFEST_URL)
            self.assertNotIn("X-Api-Key", request.headers)
            return httpx.Response(
                manifest_status,
                json={
                    "license": "https://www.si.edu/termsofuse",
                    "sequences": [{"canvases": [{"images": list(images)}]}],
                },
            )

        app = create_app(
            client_factory=lambda: httpx.AsyncClient(
                transport=httpx.MockTransport(respond)
            )
        )
        with patch.dict(os.environ, {"SMITHSONIAN_API_KEY": "offline-test-key"}):
            async with Client(app) as client:
                result = await client.call_tool(
                    TOOL, {"record_id": RECORD_ID}, raise_on_error=False
                )
        self.assertEqual(len(calls), 2 if in_scope else 1)
        return result

    async def test_per_image_usage_and_resource_dimensions(self):
        media = [
            {
                "type": "Images",
                "idsId": media_id,
                "width": 428,
                "height": 640,
                "resources": [
                    {
                        "label": "High-resolution JPEG",
                        "url": f"{IDS}/ids/download?id={media_id}.jpg",
                        "width": 514,
                        "height": 768,
                    }
                ],
            }
            for media_id in ("NMAH-front", "NMAH-back")
        ]
        media[0]["usage"] = {"access": "CC0"}
        result = await self.call(media=media, images=[manifest_image("NMAH-front")])
        self.assertFalse(result.is_error, result.content)
        self.assertEqual(result.structured_content["status"], "resolved")
        front, back = result.structured_content["images"]
        self.assertEqual(
            (front["media_id"], front["media_access"], front["usage_label"]),
            ("NMAH-front", "CC0", "CC0"),
        )
        self.assertEqual(
            (back["media_id"], back["media_access"], back["usage_label"]),
            ("NMAH-back", None, "Usage Conditions Apply"),
        )
        self.assertEqual(
            [
                (r["source"], r["declared_width"], r["declared_height"])
                for r in front["resources"]
            ],
            [("open_access", 514, 768), ("iiif", 428, 640)],
        )

    async def test_iiif_fallback_does_not_inherit_metadata_cc0(self):
        result = await self.call(images=[manifest_image("NMAH-example")])
        self.assertFalse(result.is_error, result.content)
        self.assertEqual(result.structured_content["status"], "resolved")
        (image,) = result.structured_content["images"]
        self.assertIsNone(image["media_access"])
        self.assertEqual(image["usage_label"], "Usage Conditions Apply")
        self.assertEqual(image["resources"][0]["url"], image_url("NMAH-example"))

    async def test_incomplete_discovery_and_no_assets_are_distinct(self):
        for status, expected in (
            (503, "partial"),
            (404, "no_assets"),
            (200, "no_assets"),
        ):
            with self.subTest(status=status):
                result = await self.call(manifest_status=status)
                self.assertFalse(result.is_error, result.content)
                self.assertEqual(result.structured_content["status"], expected)
                self.assertEqual(result.structured_content["images"], [])
                self.assertEqual(
                    bool(result.structured_content["warnings"]), expected == "partial"
                )

    async def test_partial_result_retains_open_access_assets(self):
        result = await self.call(
            manifest_status=503,
            media=[
                {
                    "type": "Images",
                    "idsId": "NMAH-front",
                    "usage": {"access": "Usage conditions apply"},
                    "resources": [
                        {
                            "label": "High-resolution JPEG",
                            "url": f"{IDS}/ids/download?id=NMAH-front.jpg",
                        }
                    ],
                }
            ],
        )
        self.assertFalse(result.is_error, result.content)
        self.assertEqual(result.structured_content["status"], "partial")
        (image,) = result.structured_content["images"]
        self.assertEqual(image["media_access"], "Usage conditions apply")
        self.assertEqual(image["usage_label"], "Usage Conditions Apply")
        self.assertTrue(result.structured_content["warnings"])

    async def test_out_of_scope_record_never_reaches_iiif(self):
        result = await self.call(in_scope=False)
        self.assertTrue(result.is_error)
        self.assertIn("outside the Armed Forces History scope", result.content[0].text)
