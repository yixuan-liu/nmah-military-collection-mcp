"""Serve the NMAH MCP Playground over loopback."""

import asyncio
import json
import logging
import os
import re
import sys
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import chain
from pathlib import Path
from threading import Lock
from time import perf_counter
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from nmah_military_collection_mcp.logging_config import (
    configure_project_logging,
    request_id_var,
)

logger = logging.getLogger("nmah_military_collection_mcp.playground")

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
DEFAULT_KEY = os.environ.get("SMITHSONIAN_API_KEY", "").strip()
KEY_LOCK = Lock()
MAX_IMAGE_BYTES = 24 * 1024 * 1024
key_override = ""
key_verified = False
key_revision = 0
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/style.css": ("static/style.css", "text/css; charset=utf-8"),
    "/static/main.js": ("static/main.js", "text/javascript; charset=utf-8"),
    "/static/api.js": ("static/api.js", "text/javascript; charset=utf-8"),
    "/static/search.js": ("static/search.js", "text/javascript; charset=utf-8"),
    "/static/inspect.js": ("static/inspect.js", "text/javascript; charset=utf-8"),
    "/static/image-viewer.js": (
        "static/image-viewer.js",
        "text/javascript; charset=utf-8",
    ),
    "/static/json-viewer.js": (
        "static/json-viewer.js",
        "text/javascript; charset=utf-8",
    ),
    "/static/api-key.js": ("static/api-key.js", "text/javascript; charset=utf-8"),
    "/static/tool-connections.js": (
        "static/tool-connections.js",
        "text/javascript; charset=utf-8",
    ),
}
ROUTES = {
    "/api/search": "search_nmah_military_objects",
    "/api/metadata": "get_nmah_military_object_metadata",
    "/api/image-assets": "get_nmah_military_object_image_assets",
}


def key_status():
    return {
        "configured": bool(key_override or DEFAULT_KEY),
        "source": "debugger" if key_override else "project" if DEFAULT_KEY else None,
        "verified": key_verified,
    }


def verify_key(candidate):
    started = perf_counter()
    try:
        response = httpx.get(
            "https://api.si.edu/openaccess/api/v1.0/search",
            params={"q": "*", "rows": 1},
            headers={"X-Api-Key": candidate},
            timeout=10,
        )
    except httpx.RequestError as exc:
        logger.warning("key_verification_failed error_type=%s", type(exc).__name__)
        return {"error": "Could not reach Smithsonian Open Access. Try again."}, 502

    logger.log(
        logging.WARNING if response.is_error else logging.DEBUG,
        "key_verification_response status=%d elapsed_ms=%.1f",
        response.status_code,
        (perf_counter() - started) * 1000,
    )

    if response.status_code in (401, 403):
        return {"error": "Smithsonian rejected the API key."}, 422
    if response.status_code == 429:
        return {"error": "Smithsonian is rate limiting requests. Try again later."}, 429
    try:
        payload = response.json()
        if (
            response.is_success
            and isinstance(payload, dict)
            and payload.get("status") == 200
            and payload.get("responseCode") == 1
            and isinstance(payload.get("response"), dict)
        ):
            return None
    except ValueError:
        pass
    return {
        "error": "Smithsonian did not return a valid search response. Try again."
    }, 502


def configure_key(arguments):
    global key_override, key_verified, key_revision
    if arguments == {"reveal": True}:
        with KEY_LOCK:
            key = key_override or DEFAULT_KEY
        if not key:
            return {"error": "No API key is configured."}, 404
        return {"key": key}, 200

    if arguments == {"use_default": True}:
        with KEY_LOCK:
            key_override = ""
            key_verified = False
            key_revision += 1
            return key_status(), 200

    candidate = arguments.get("key")
    if arguments and (
        set(arguments) != {"key"}
        or not isinstance(candidate, str)
        or not re.fullmatch(r"[!-~]{1,256}", candidate)
    ):
        return {"error": "Enter a valid Smithsonian API key."}, 400

    with KEY_LOCK:
        key = candidate or key_override or DEFAULT_KEY
        if not key:
            return {"error": "Enter a Smithsonian API key to verify."}, 400
        key_revision += 1
        revision = key_revision

    failure = verify_key(key)
    with KEY_LOCK:
        if revision != key_revision:
            return {
                "error": "Another key operation started. Check the current settings and try again."
            }, 409
        if failure:
            if key == (key_override or DEFAULT_KEY):
                key_verified = False
            return failure
        if candidate:
            key_override = candidate
        key_verified = True
        return key_status(), 200


def mcp_client(key=""):
    log_env = {
        name: os.environ[name]
        for name in ("LOG_LEVEL", "FASTMCP_LOG_LEVEL")
        if name in os.environ
    }
    return Client(
        StdioTransport(
            command=sys.executable,
            args=["-m", "nmah_military_collection_mcp"],
            cwd=str(PROJECT),
            env={
                "SMITHSONIAN_API_KEY": key,
                "PYTHONDONTWRITEBYTECODE": "1",
                "FASTMCP_SHOW_SERVER_BANNER": "false",
                **log_env,
            },
        )
    )


async def discover():
    async with mcp_client() as client:
        return {
            "tools": [
                tool.model_dump(mode="json", by_alias=True)
                for tool in await client.list_tools()
                if tool.name in ROUTES.values()
            ]
        }


async def call_tool(tool, arguments, key, request_id):
    async with mcp_client(key) as client:
        result = await client.call_tool(
            tool, arguments, raise_on_error=False, meta={"request_id": request_id}
        )
    if result.is_error:
        return {
            "error": "\n".join(
                item.text for item in result.content if item.type == "text"
            )
        }, 422
    return result.structured_content, 200


@contextmanager
def open_image(query):
    """Open only the supported Smithsonian image routes."""
    args = parse_qs(query, strict_parsing=True)
    if set(args) != {"id", "kind"} or any(len(values) != 1 for values in args.values()):
        raise ValueError("Invalid image request.")
    media_id, kind = args["id"][0], args["kind"][0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", media_id):
        raise ValueError("Invalid media identifier.")
    if kind in ("thumbnail", "preview"):
        path = "/ids/deliveryService"
        params = {"id": media_id, "max": "240" if kind == "thumbnail" else "1200"}
    elif kind == "open_access":
        path = "/ids/download"
        params = {"id": f"{media_id}.jpg"}
    elif kind == "iiif":
        path = f"/ids/iiif/{media_id}/full/full/0/default.jpg"
        params = None
    else:
        raise ValueError("Unsupported image resource.")

    with httpx.stream(
        "GET", f"https://ids.si.edu{path}", params=params, timeout=20
    ) as response:
        if kind != "open_access" or not response.is_redirect:
            yield kind, response
            return
        location = open_access_redirect(response, f"{media_id}.jpg")

    with httpx.stream("GET", location, timeout=20) as response:
        yield kind, response


def open_access_redirect(response, filename):
    location = response.headers.get("location", "")
    target = urlsplit(location)
    if (
        target.scheme != "https"
        or target.netloc != "smithsonian-open-access.s3-us-west-2.amazonaws.com"
        or target.path != f"/media/nmah/{filename}"
    ):
        raise ValueError("Unsupported Smithsonian image redirect.")
    return location


def file_size(query):
    """Read the original file's byte count without fetching its body."""
    args = parse_qs(query, strict_parsing=True)
    if set(args) != {"file"} or len(args["file"]) != 1:
        raise ValueError("Invalid file request.")
    filename = args["file"][0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}\.(?:jpg|jpeg|tif|tiff)", filename):
        raise ValueError("Invalid image filename.")

    def total_bytes(response):
        response.raise_for_status()
        if response.status_code == 206:
            match = re.fullmatch(
                r"bytes 0-0/([1-9][0-9]*)", response.headers.get("content-range", "")
            )
            return int(match[1]) if match else None
        length = response.headers.get("content-length", "")
        return int(length) if length.isascii() and length.isdigit() else None

    headers = {"Range": "bytes=0-0", "Accept-Encoding": "identity"}
    with httpx.stream(
        "GET",
        "https://ids.si.edu/ids/download",
        params={"id": filename},
        headers=headers,
        timeout=8,
    ) as response:
        if not response.is_redirect:
            return total_bytes(response)
        location = open_access_redirect(response, filename)

    with httpx.stream("GET", location, headers=headers, timeout=8) as response:
        return total_bytes(response)


def jpeg_chunks(response):
    response.raise_for_status()
    length = response.headers.get("content-length", "")
    if (
        "content-encoding" not in response.headers
        and length.isascii()
        and length.isdecimal()
        and int(length) > MAX_IMAGE_BYTES
    ):
        raise ValueError("Image is too large to preview.")

    chunks = response.iter_bytes()
    first = next(chunks, b"")
    while len(first) < 3:
        chunk = next(chunks, b"")
        if not chunk:
            break
        first += chunk
    if not first.startswith(b"\xff\xd8\xff"):
        raise ValueError("Smithsonian did not return a JPEG.")

    size = 0
    for chunk in chain((first,), chunks):
        size += len(chunk)
        if size > MAX_IMAGE_BYTES:
            raise ValueError("Image is too large to preview.")
        yield chunk


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, value, status=200, content_type="application/json", *, secret=""):
        if isinstance(value, bytes):
            body = value
        else:
            serialized = json.dumps(value, ensure_ascii=False)
            if secret:
                encoded_secret = json.dumps(secret, ensure_ascii=False)[1:-1]
                serialized = serialized.replace(encoded_secret, "[REDACTED]")
            body = serialized.encode()
        request_id = request_id_var.get()
        if request_id and status in (400, 403, 428):
            logger.info(
                "playground_tool_rejected tool=%s status=%d",
                ROUTES[self.path],
                status,
            )
        self.send_response(status)
        if request_id:
            self.send_header("X-Request-ID", request_id)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def send_jpeg_stream(self, first, chunks):
        chunked = self.request_version == "HTTP/1.1"
        if chunked:
            self.protocol_version = "HTTP/1.1"
        self.close_connection = True
        try:
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            if chunked:
                self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for chunk in chain((first,), chunks):
                if chunked:
                    self.wfile.write(f"{len(chunk):x}\r\n".encode("ascii"))
                self.wfile.write(chunk)
                if chunked:
                    self.wfile.write(b"\r\n")
            if chunked:
                self.wfile.write(b"0\r\n\r\n")
        except (BrokenPipeError, ConnectionResetError):
            return
        except (httpx.HTTPError, ValueError) as exc:
            # Headers have been sent. Close without a final chunk to signal truncation.
            logger.warning("iiif_stream_interrupted error_type=%s", type(exc).__name__)

    def local_request(self):
        host = f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Host") == host and self.headers.get("Origin") in (
            None,
            f"http://{host}",
        )

    def do_GET(self):
        if not self.local_request():
            return self.send({"error": "Local origin required."}, 403)
        target = urlsplit(self.path)
        if target.path == "/api/image-size":
            try:
                return self.send({"bytes": file_size(target.query)})
            except ValueError:
                return self.send({"error": "Invalid Smithsonian image resource."}, 400)
            except httpx.HTTPError:
                return self.send({"bytes": None})
        if target.path == "/api/image-preview":
            try:
                with open_image(target.query) as (kind, response):
                    chunks = jpeg_chunks(response)
                    if kind == "iiif":
                        return self.send_jpeg_stream(next(chunks), chunks)
                    return self.send(b"".join(chunks), content_type="image/jpeg")
            except ValueError as error:
                return self.send({"error": str(error)}, 400)
            except httpx.HTTPError:
                return self.send(
                    {"error": "Could not load the Smithsonian image."}, 502
                )
        try:
            if self.path in STATIC_FILES:
                filename, content_type = STATIC_FILES[self.path]
                return self.send(
                    (BASE / filename).read_bytes(), content_type=content_type
                )
            if self.path == "/api/api-key":
                with KEY_LOCK:
                    status = key_status()
                return self.send(status)
            if self.path == "/api/schema":
                return self.send(asyncio.run(discover()))
            return self.send({"error": "Not found."}, 404)
        except Exception as exc:
            logger.error(
                "playground_request_failed method=GET error_type=%s", type(exc).__name__
            )
            return self.send(
                {"error": "Could not connect to the local MCP server."}, 500
            )

    def do_POST(self):
        tool = ROUTES.get(self.path)
        request_id = uuid4().hex if tool is not None else None
        token = request_id_var.set(request_id)
        try:
            self._handle_post(tool, request_id)
        finally:
            request_id_var.reset(token)

    def _handle_post(self, tool, request_id):
        if not self.local_request():
            return self.send({"error": "Local origin required."}, 403)
        if tool is None and self.path != "/api/api-key":
            return self.send({"error": "Not found."}, 404)
        if self.path == "/api/api-key":
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if (
                self.headers.get("Origin") != origin
                or self.headers.get_content_type() != "application/json"
            ):
                return self.send(
                    {"error": "A same-origin JSON request is required."}, 403
                )
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                return self.send({"error": "Invalid request size."}, 400)
            arguments = json.loads(self.rfile.read(size))
            if not isinstance(arguments, dict):
                return self.send({"error": "Expected a JSON object."}, 400)
        except (ValueError, UnicodeDecodeError):
            return self.send({"error": "Invalid JSON request."}, 400)
        started = perf_counter()
        try:
            if self.path == "/api/api-key":
                data, status = configure_key(arguments)
                return self.send(data, status)
            with KEY_LOCK:
                key = key_override or DEFAULT_KEY
            if not key:
                return self.send(
                    {"error": "Set a Smithsonian API key to run this tool."}, 428
                )
            data, status = asyncio.run(call_tool(tool, arguments, key, request_id))
            logger.info(
                "playground_tool_response tool=%s status=%d elapsed_ms=%.1f",
                tool,
                status,
                (perf_counter() - started) * 1000,
            )
            return self.send(data, status, secret=key)
        except Exception as exc:
            logger.error(
                "playground_request_failed method=POST tool=%s error_type=%s",
                tool or "verify_key",
                type(exc).__name__,
            )
            return self.send(
                {"error": "The MCP tool could not complete the request."}, 502
            )


if __name__ == "__main__":
    configure_project_logging()
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        print(
            f"NMAH MCP Playground: http://127.0.0.1:{server.server_port}/", flush=True
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
