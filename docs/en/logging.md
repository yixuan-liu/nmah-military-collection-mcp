# Application logging and live stdio verification

[中文版](../zh/logging.md) · [Documentation index](README.md)

## Configuration

Set `LOG_LEVEL` in the project root’s `.env` using the [environment template](../../.env.example). The MCP server and Playground both accept `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`. An unset, blank, or invalid value falls back to `INFO`. Each process reads the setting at startup, so restart after changing it.

```dotenv
LOG_LEVEL=INFO
```

Run either entry point from the project root.

```sh
uv run --locked --env-file .env python -m nmah_military_collection_mcp
uv run --locked --env-file .env python playground/server.py
```

Playground forwards `LOG_LEVEL` to its MCP subprocess. When an external MCP client launches the server, configure that launch command to load the same file or supply `LOG_LEVEL` in the child environment. FastMCP framework logging has a separate setting, `FASTMCP_LOG_LEVEL`. To enable DEBUG for one Playground run, set the variable on the launch command.

```sh
LOG_LEVEL=DEBUG uv run --locked --env-file .env python playground/server.py
```

Application logs have a timestamp, level, logger name, and event fields. They go to `stderr`. The MCP server reserves `stdout` for JSON-RPC messages. Application log events omit API keys, request headers, search text, full request URLs, and response bodies.

## What each layer records

| Layer | Events |
| --- | --- |
| MCP tools (`tools`) | `DEBUG` records the requested page size and offset. `INFO` records tool completion, elapsed time, and result counts. Image discovery also reports its status and warning count, and logs `partial` at `WARNING`. |
| MCP upstream client (`api_client`) | `DEBUG` records the upstream endpoint category, HTTP status, and elapsed time for ordinary responses. `WARNING` covers failures such as rate limiting, transport errors, and invalid upstream responses. An HTTP `404` is logged at `DEBUG`. |
| Playground bridge (`playground`) | `INFO` records the tool name, local HTTP response status, and total bridge time. API key verification logs the upstream status and elapsed time, at `DEBUG` for successful HTTP responses and `WARNING` for HTTP errors. Unexpected bridge exceptions log the operation and exception type at `ERROR`. |

The Playground tool duration covers the bridge call, including starting and connecting to the MCP subprocess. MCP upstream durations measure individual HTTP calls to Smithsonian services.

## Match a Playground request to MCP logs

Each tool POST to `/api/search`, `/api/metadata`, or `/api/image-assets` gets a fresh `X-Request-ID` response header. Copy the header value from the browser’s Network panel and search stderr for `request_id=<value>`. Both the bridge and the MCP tool and upstream logs use the same value, even when concurrent requests finish in a different order.

The bridge sends the ID as `meta.request_id` in the MCP tool call. It is a 32-character lowercase hexadecimal UUID. MCP accepts a valid value and generates a fresh one for direct calls with absent or invalid metadata. The request ID lives in the current thread or async context and is restored when the call finishes. Application events outside a tool request show `request_id=-`. The field applies to project logs. Framework logging retains its own format.

For a request rejected before tool dispatch, the ID connects the HTTP response to the bridge log. For a dispatched request, the upstream HTTP status and the local Playground HTTP status can differ. The following abbreviated example illustrates the simulated rate-limit case.

```text
WARNING nmah_military_collection_mcp.api_client: request_id=7f8c9b3a1e2d4a6c8f0123456789abcd upstream_response endpoint=search status=429 elapsed_ms=4.2
INFO nmah_military_collection_mcp.playground: request_id=7f8c9b3a1e2d4a6c8f0123456789abcd playground_tool_response tool=search_nmah_military_objects status=422 elapsed_ms=285.0
```

The [offline logging tests](../../tests/test_logging.py) exercise the local HTTP bridge and real MCP stdio transport with a simulated upstream. The second request finishes first with upstream `429` and local `422`. The test checks that the first request still returns `200`, both response IDs match their own logs, and private test values are absent from the logs.

## Live verification with `nmah_446333`

On November 8, 2026, a temporary Playground process loaded the existing `.env` and used `LOG_LEVEL=DEBUG` for that run. The verification called the local Playground HTTP endpoints, which used a real MCP stdio client and live Smithsonian services.

| Playground endpoint | Live result | MCP upstream time | MCP tool time | Playground time |
| --- | --- | --- | --- | --- |
| `POST /api/search` | HTTP `200`. The query `nmah_446333` matched and returned one record, whose ID matched. | Open Access search `200`, 499.1 ms | 499.7 ms | 1,253.2 ms |
| `POST /api/metadata` | HTTP `200`. The returned catalog ID matched `nmah_446333`. | Open Access content `200`, 441.8 ms | 442.1 ms | 1,169.5 ms |
| `POST /api/image-assets` | HTTP `200`. Status `resolved`, one image, zero warnings. | Open Access content `200`, 468.5 ms. IIIF manifest `200`, 307.5 ms. | 777.4 ms | 1,502.6 ms |

`GET /api/schema` returned HTTP `200` and discovered all three tools. The bridge decoded all three tool results as structured data over stdio. Both layers’ application logs were captured on `stderr`, and a check of the captured stream found no API key. The timings are observations from this run. The temporary process was stopped after verification.

These lines show the image lookup across both layers. This live run predates the request ID field.

```text
2026-11-08 22:27:57,229 DEBUG nmah_military_collection_mcp.api_client: upstream_response endpoint=content status=200 elapsed_ms=468.5
2026-11-08 22:27:57,537 DEBUG nmah_military_collection_mcp.api_client: upstream_response endpoint=iiif_manifest status=200 elapsed_ms=307.5
2026-11-08 22:27:57,538 INFO nmah_military_collection_mcp.tools: tool_completed tool=get_nmah_military_object_image_assets status=resolved returned=1 warnings=0 elapsed_ms=777.4
2026-11-08 22:27:57,689 INFO nmah_military_collection_mcp.playground: playground_tool_response tool=get_nmah_military_object_image_assets status=200 elapsed_ms=1502.6
```

The [offline logging tests](../../tests/test_logging.py) use simulated HTTP `200` and `429` responses to verify log level filtering, omission of sensitive values, and MCP discovery and calls over stdio.

## Concurrent live verification with `nmah_446333`

On November 9, 2026, a temporary Playground instance loaded the existing `.env` with `LOG_LEVEL=DEBUG`. Three local HTTP requests ran concurrently against live Smithsonian services through MCP stdio. Each returned HTTP `200` and a distinct `X-Request-ID`. Each header value matched the `request_id` in the corresponding Playground response log and in all MCP tool and upstream logs for that call.

| Playground request | `X-Request-ID` | Verified result |
| --- | --- | --- |
| `POST /api/search` | `ef6e84a5bcbc408eb5e520ecb6f2cabc` | One match, and the returned record ID was `nmah_446333`. |
| `POST /api/metadata` | `eccfe16b11ee4374b08568bb0d562260` | The returned catalog ID matched `nmah_446333`. |
| `POST /api/image-assets` | `25a772637fb94a079b5f0fb9305e3a5d` | Open Access content and the IIIF manifest both returned `200`. The tool reported `resolved`, one image, and zero warnings. |

Stdio discovery returned all three tools, and the bridge decoded structured results from all three calls. The responses finished in the order shown in the table. The logs interleaved, with image content logged before metadata content, while the IDs kept the two calls distinguishable. The credential check found no API key in captured `stderr`. The temporary instance was stopped after the run.

The log lines below are sorted by timestamp, with both layers shown together.

```text
2026-11-09 09:01:54,301 DEBUG nmah_military_collection_mcp.tools: request_id=ef6e84a5bcbc408eb5e520ecb6f2cabc search_page rows=3 offset=0
2026-11-09 09:01:54,658 DEBUG nmah_military_collection_mcp.api_client: request_id=ef6e84a5bcbc408eb5e520ecb6f2cabc upstream_response endpoint=search status=200 elapsed_ms=357.3
2026-11-09 09:01:54,659 INFO nmah_military_collection_mcp.tools: request_id=ef6e84a5bcbc408eb5e520ecb6f2cabc tool_completed tool=search_nmah_military_objects returned=1 total=1 elapsed_ms=357.9
2026-11-09 09:01:54,805 DEBUG nmah_military_collection_mcp.api_client: request_id=25a772637fb94a079b5f0fb9305e3a5d upstream_response endpoint=content status=200 elapsed_ms=504.5
2026-11-09 09:01:54,825 DEBUG nmah_military_collection_mcp.api_client: request_id=eccfe16b11ee4374b08568bb0d562260 upstream_response endpoint=content status=200 elapsed_ms=524.7
2026-11-09 09:01:54,825 INFO nmah_military_collection_mcp.tools: request_id=eccfe16b11ee4374b08568bb0d562260 tool_completed tool=get_nmah_military_object_metadata returned=1 elapsed_ms=524.9
2026-11-09 09:01:54,856 INFO nmah_military_collection_mcp.playground: request_id=ef6e84a5bcbc408eb5e520ecb6f2cabc playground_tool_response tool=search_nmah_military_objects status=200 elapsed_ms=1173.7
2026-11-09 09:01:54,954 INFO nmah_military_collection_mcp.playground: request_id=eccfe16b11ee4374b08568bb0d562260 playground_tool_response tool=get_nmah_military_object_metadata status=200 elapsed_ms=1271.3
2026-11-09 09:01:55,117 DEBUG nmah_military_collection_mcp.api_client: request_id=25a772637fb94a079b5f0fb9305e3a5d upstream_response endpoint=iiif_manifest status=200 elapsed_ms=311.4
2026-11-09 09:01:55,117 INFO nmah_military_collection_mcp.tools: request_id=25a772637fb94a079b5f0fb9305e3a5d tool_completed tool=get_nmah_military_object_image_assets status=resolved returned=1 warnings=0 elapsed_ms=816.4
2026-11-09 09:01:55,257 INFO nmah_military_collection_mcp.playground: request_id=25a772637fb94a079b5f0fb9305e3a5d playground_tool_response tool=get_nmah_military_object_image_assets status=200 elapsed_ms=1574.4
```
