"""Verify the MCP contract over stdio and optionally compare live API pages."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from nmah_military_collection_mcp.app import SERVER_INSTRUCTIONS

TOOL = "search_nmah_military_objects"
METADATA_TOOL = "get_nmah_military_object_metadata"
IMAGE_ASSETS_TOOL = "get_nmah_military_object_image_assets"


async def main(live: bool) -> None:
    key = os.environ.get("SMITHSONIAN_API_KEY", "").strip() if live else ""
    if live and not key:
        raise SystemExit("Set SMITHSONIAN_API_KEY to run the live check.")
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "nmah_military_collection_mcp"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env={
            "SMITHSONIAN_API_KEY": key,
            "FASTMCP_SHOW_SERVER_BANNER": "false",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    report = {"mode": "live" if live else "offline"}
    async with Client(transport) as client:
        assert client.instructions == SERVER_INSTRUCTIONS
        report["server_instructions"] = "passed"
        tools = await client.list_tools()
        by_name = {tool.name: tool for tool in tools}
        assert set(by_name) == {TOOL, METADATA_TOOL, IMAGE_ASSETS_TOOL}
        image_tool = by_name[IMAGE_ASSETS_TOOL]
        assert image_tool.input_schema["required"] == ["record_id"]
        assert image_tool.input_schema["additionalProperties"] is False
        assert image_tool.annotations.read_only_hint is True
        output = image_tool.output_schema["properties"]
        assert output["status"]["enum"] == ["resolved", "partial", "no_assets"]
        assert "usage_label" in output["images"]["items"]["required"]
        metadata_schema = by_name[METADATA_TOOL].input_schema
        assert metadata_schema["required"] == ["record_id"]
        assert set(metadata_schema["properties"]) == {"record_id"}
        properties = by_name[TOOL].input_schema["properties"]
        assert set(properties) == {
            "query",
            "branch",
            "rows",
            "offset",
            "date",
            "has_images",
        }
        assert properties["branch"]["anyOf"][0]["enum"] == [
            "Army",
            "Navy",
            "Air Force",
            "Marine Corps",
            "Coast Guard",
        ]
        assert properties["date"]["anyOf"][0]["enum"] == [
            f"{year}s" for year in range(1770, 2001, 10)
        ]
        assert (
            properties["rows"]["minimum"] == 1 and properties["rows"]["maximum"] == 50
        )
        assert (
            properties["offset"]["minimum"] == 0
            and properties["offset"]["default"] == 0
        )
        assert properties["has_images"]["type"] == "boolean"
        assert properties["has_images"]["default"] is False
        assert properties["query"]["default"] == ""
        invalid = [
            {"branch": "USMC"},
            {"branch": "Unknown"},
            {"rows": 0},
            {"rows": 51},
            {"offset": -1},
            {"offset": 1.5},
            {"date": "1914"},
            {"date": "1760s"},
            {"date": "2010s"},
        ]
        for arguments in invalid:
            result = await client.call_tool(TOOL, arguments, raise_on_error=False)
            assert result.is_error, arguments
            assert "validation error" in result.content[0].text, result.content
        report.update(schema="passed", invalid_inputs=len(invalid))
        if not live:
            result = await client.call_tool(TOOL, {}, raise_on_error=False)
            assert result.is_error and "SMITHSONIAN_API_KEY" in result.content[0].text
            result = await client.call_tool(
                METADATA_TOOL, {"record_id": "nmah_463569"}, raise_on_error=False
            )
            assert result.is_error and "SMITHSONIAN_API_KEY" in result.content[0].text
            result = await client.call_tool(
                IMAGE_ASSETS_TOOL, {"record_id": "nmah_463569"}, raise_on_error=False
            )
            assert result.is_error and "SMITHSONIAN_API_KEY" in result.content[0].text
            report["missing_key"] = "passed"
        else:
            async with httpx.AsyncClient(
                timeout=45, headers={"X-Api-Key": key}
            ) as http:

                async def search(arguments):
                    result = await client.call_tool(TOOL, arguments)
                    page = result.data
                    response = await http.get(
                        "https://api.si.edu/openaccess/api/v1.0/search",
                        params={
                            "q": page["applied_query"],
                            "fqs": json.dumps(page["applied_filters"]),
                            "rows": arguments.get("rows", 10),
                            "start": arguments.get("offset", 0),
                            "sort": "id",
                        },
                    )
                    response.raise_for_status()
                    envelope = response.json()
                    assert envelope["status"] == 200 and envelope["responseCode"] == 1
                    direct = envelope["response"]
                    ids = [
                        row["content"]["descriptiveNonRepeating"]["record_ID"]
                        for row in page["objects"]
                    ]
                    assert page["total_count"] == direct["rowCount"]
                    assert page["objects"] == direct["rows"]
                    assert page["offset"] == arguments.get("offset", 0)
                    return page, ids

                metadata = (
                    await client.call_tool(METADATA_TOOL, {"record_id": "nmah_463569"})
                ).data
                direct_content = await http.get(
                    "https://api.si.edu/openaccess/api/v1.0/content/edanmdm%3Anmah_463569"
                )
                direct_content.raise_for_status()
                assert metadata == direct_content.json()["response"]
                report["live_metadata"] = "passed"
                image_checks = {}
                for record_id, media_id, source, size, access, label in (
                    (
                        "nmah_446333",
                        "NMAH-2004-46240",
                        "open_access",
                        (514, 768),
                        "CC0",
                        "CC0",
                    ),
                    (
                        "nmah_463569",
                        "NMAH-AHB2010q67926",
                        "iiif",
                        (3000, 2250),
                        None,
                        "Usage Conditions Apply",
                    ),
                ):
                    result = await client.call_tool(
                        IMAGE_ASSETS_TOOL, {"record_id": record_id}
                    )
                    assets = result.structured_content
                    assert (
                        assets["record_id"] == record_id
                        and assets["status"] == "resolved"
                    ), assets
                    (image,) = [
                        entry
                        for entry in assets["images"]
                        if entry["media_id"] == media_id
                    ]
                    assert (
                        image["media_access"] == access
                        and image["usage_label"] == label
                    )
                    resource = next(
                        item
                        for item in image["resources"]
                        if item["format"] == "jpeg" and item["source"] == source
                    )
                    assert (
                        resource["declared_width"],
                        resource["declared_height"],
                    ) == size
                    assert image["resources"][0] == resource
                    image_checks[record_id] = {
                        "media_id": media_id,
                        "preferred_jpeg_source": source,
                        "declared_size": size,
                        "usage_label": label,
                    }
                report["live_image_assets"] = image_checks
                arguments = {
                    "branch": "Army",
                    "date": "1910s",
                    "has_images": True,
                    "rows": 3,
                }
                first, first_ids = await search(arguments)
                second, second_ids = await search({**arguments, "offset": 3})
                combined, combined_ids = await search({**arguments, "rows": 6})
                assert first["applied_query"] == "*"
                assert first["next_offset"] == 3 and second["next_offset"] == 6
                assert len(set(first_ids + second_ids)) == 6
                assert first_ids + second_ids == combined_ids
                for row in combined["objects"]:
                    indexed = row["content"]["indexedStructured"]
                    assert (
                        "1910s" in indexed["date"]
                        and "Images" in indexed["online_media_type"]
                    )
                cap, ids = await search({"query": "nmah_400783", "has_images": True})
                assert ids == ["nmah_400783"] and cap["next_offset"] is None
                report["live"] = {
                    "total_count": first["total_count"],
                    "unique_page_ids": combined_ids,
                    "direct_api_comparison": "passed",
                    "known_image_record": ids[0],
                }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    asyncio.run(main(parser.parse_args().live))
