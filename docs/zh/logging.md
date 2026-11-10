# 应用日志配置与 stdio 实测

[English version](../en/logging.md) · [文档目录](README.md)

## 日志配置

参照[环境变量模板](../../.env.example)，在项目根目录的 `.env` 中设置 `LOG_LEVEL`。MCP 服务与 Playground 共用该变量，支持 `DEBUG`、`INFO`、`WARNING`、`ERROR` 和 `CRITICAL`。变量未设置、为空或无效时使用 `INFO`。两个进程都在启动时读取配置，修改后重启生效。

```dotenv
LOG_LEVEL=INFO
```

在项目根目录运行所需的启动命令。

```sh
uv run --locked --env-file .env python -m nmah_military_collection_mcp
uv run --locked --env-file .env python playground/server.py
```

Playground 会把 `LOG_LEVEL` 传给 MCP 子进程。如果由外部 MCP 客户端启动服务，可让启动命令加载同一份 `.env`，或在子进程的环境中提供 `LOG_LEVEL`。FastMCP 框架日志由 `FASTMCP_LOG_LEVEL` 单独控制。仅本次启动使用 DEBUG 时，可以在命令前设置环境变量。

```sh
LOG_LEVEL=DEBUG uv run --locked --env-file .env python playground/server.py
```

应用日志包含时间戳、级别、logger 名称和事件字段，统一写入 `stderr`。MCP 服务的 `stdout` 用于传输 JSON-RPC 消息。应用日志省略 API Key、请求头、原始检索词、完整请求 URL 和响应体。

## 两层各记录什么

| 日志来源 | 记录内容 |
| --- | --- |
| MCP 工具层（`tools`） | `DEBUG` 记录分页大小与偏移量。 `INFO` 记录工具完成、耗时和结果数量。图片清单另记状态和警告数，`partial` 按 `WARNING` 记录。 |
| MCP 上游客户端（`api_client`） | `DEBUG` 记录常规上游响应的接口类别、HTTP 状态码和耗时。 `WARNING` 记录限流、网络错误或上游响应格式异常等情况。HTTP `404` 按 `DEBUG` 记录。 |
| Playground bridge（`playground`） | `INFO` 记录工具名、本地 HTTP 状态码和 bridge 总耗时。API Key 验证记录上游状态码和耗时，HTTP 成功响应使用 `DEBUG`，HTTP 错误响应使用 `WARNING`。bridge 遇到未预期异常时，`ERROR` 记录操作和异常类型。 |

Playground 的工具耗时包含启动并连接 MCP 子进程的时间。MCP 上游耗时对应各次发往 Smithsonian 服务的 HTTP 请求。

## 用 Request ID 对应两层日志

每次向 `/api/search`、`/api/metadata` 或 `/api/image-assets` 发起工具请求，HTTP 响应都会带上新的 `X-Request-ID`。在浏览器 Network 面板复制该值，再到 stderr 搜索 `request_id=<值>`，即可找到这次请求的 Playground、MCP 工具和上游日志。即使多个请求并发、完成顺序颠倒，也能逐条对应。

Playground 通过 MCP 工具调用的 `meta.request_id` 传递这个 32 位小写十六进制 UUID。外部客户端直接调用 MCP 时，如果缺少 ID 或格式无效，服务端会生成一个。ID 绑定到当前线程或异步上下文，调用结束后恢复。工具请求之外的应用日志显示 `request_id=-`。FastMCP 框架日志仍采用自己的格式。

如果请求在进入 MCP 前就被拒绝，可用响应头中的 ID 查到 Playground 日志。请求进入 MCP 后，馆方响应状态码和 Playground 的 HTTP 状态码可能不同。下面是模拟限流场景的简化示例。

```text
WARNING nmah_military_collection_mcp.api_client: request_id=7f8c9b3a1e2d4a6c8f0123456789abcd upstream_response endpoint=search status=429 elapsed_ms=4.2
INFO nmah_military_collection_mcp.playground: request_id=7f8c9b3a1e2d4a6c8f0123456789abcd playground_tool_response tool=search_nmah_military_objects status=422 elapsed_ms=285.0
```

[离线日志测试](../../tests/test_logging.py)使用本地 HTTP bridge 和真实 MCP stdio 传输，只模拟 Smithsonian 上游。后发请求先完成，上游返回 `429`，Playground 返回 `422`。测试确认先发请求仍返回 `200`，两个响应 ID 各自对应正确的两层日志，日志里没有用于测试的敏感值。

## `nmah_446333` 真实调用与验证

2026 年 11 月 8 日，使用现有 `.env` 启动临时 Playground，仅为本次进程设置 `LOG_LEVEL=DEBUG`。验证请求通过本地 Playground HTTP 接口进入 bridge，再经 MCP stdio 调用真实的 Smithsonian 服务。

| Playground 接口 | 实测结果 | MCP 上游耗时 | MCP 工具耗时 | Playground 耗时 |
| --- | --- | --- | --- | --- |
| `POST /api/search` | HTTP `200`。以 `nmah_446333` 搜索，命中并返回 1 条，编号一致。 | Open Access search `200`，499.1 ms | 499.7 ms | 1,253.2 ms |
| `POST /api/metadata` | HTTP `200`。返回的藏品编号与 `nmah_446333` 一致。 | Open Access content `200`，441.8 ms | 442.1 ms | 1,169.5 ms |
| `POST /api/image-assets` | HTTP `200`。状态为 `resolved`，1 张图，0 条警告。 | Open Access content `200`，468.5 ms。IIIF manifest `200`，307.5 ms。 | 777.4 ms | 1,502.6 ms |

`GET /api/schema` 返回 HTTP `200`，发现全部三个工具。bridge 通过 stdio 成功解析了三次调用的结构化结果。两层应用日志均从 `stderr` 捕获，检查确认其中没有 API Key。表中耗时为本次观察值，临时进程在验证后关闭。

以下为图片清单调用的实测日志节选，采集时尚未加入 request ID 字段。

```text
2026-11-08 22:27:57,229 DEBUG nmah_military_collection_mcp.api_client: upstream_response endpoint=content status=200 elapsed_ms=468.5
2026-11-08 22:27:57,537 DEBUG nmah_military_collection_mcp.api_client: upstream_response endpoint=iiif_manifest status=200 elapsed_ms=307.5
2026-11-08 22:27:57,538 INFO nmah_military_collection_mcp.tools: tool_completed tool=get_nmah_military_object_image_assets status=resolved returned=1 warnings=0 elapsed_ms=777.4
2026-11-08 22:27:57,689 INFO nmah_military_collection_mcp.playground: playground_tool_response tool=get_nmah_military_object_image_assets status=200 elapsed_ms=1502.6
```

[离线日志测试](../../tests/test_logging.py)使用模拟 HTTP `200` 和 `429` 响应，检查日志级别过滤、敏感值省略，以及经 stdio 发现和调用工具。

## `nmah_446333` 并发实测

2026 年 11 月 9 日，临时 Playground 实例加载现有 `.env`，并以 `LOG_LEVEL=DEBUG` 启动。三个本地 HTTP 请求并发发出，经 MCP stdio 调用真实的 Smithsonian 服务。三个请求均返回 HTTP `200`，各自的 `X-Request-ID` 互不相同，且与对应的 Playground 响应日志、MCP 工具日志和上游请求日志中的 `request_id` 一致。

| Playground 请求 | `X-Request-ID` | 核对结果 |
| --- | --- | --- |
| `POST /api/search` | `ef6e84a5bcbc408eb5e520ecb6f2cabc` | 命中并返回 1 条，藏品编号为 `nmah_446333`。 |
| `POST /api/metadata` | `eccfe16b11ee4374b08568bb0d562260` | 返回的藏品编号与 `nmah_446333` 一致。 |
| `POST /api/image-assets` | `25a772637fb94a079b5f0fb9305e3a5d` | Open Access content 与 IIIF manifest 均返回 `200`。清单状态为 `resolved`，1 张图，0 条警告。 |

stdio 工具发现返回全部三个工具，bridge 成功解析了三次调用的结构化结果。响应按表中顺序完成。日志出现交错，图片清单的 content 日志先于元数据的 content 日志写入，仍可用各自的 ID 区分。检查确认捕获的 `stderr` 不含 API Key。临时实例在实测后关闭。

以下按时间戳合并展示两层实测日志。

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
