import re
from collections.abc import Callable
from uuid import uuid4

import httpx
from fastmcp import Context
from fastmcp.server.lifespan import lifespan
from fastmcp.server.middleware import Middleware

from .api_client import SmithsonianAPIClient
from .config import REQUEST_TIMEOUT
from .logging_config import request_id_var


class RequestIDMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        ctx = context.fastmcp_context
        request = ctx.request_context if ctx is not None else None
        candidate = (request.meta or {}).get("request_id") if request else None
        request_id = (
            candidate
            if isinstance(candidate, str) and re.fullmatch(r"[0-9a-f]{32}", candidate)
            else uuid4().hex
        )
        token = request_id_var.set(request_id)
        try:
            return await call_next(context)
        finally:
            request_id_var.reset(token)


def make_lifespan(client_factory: Callable[[], httpx.AsyncClient] | None = None):
    """Own one HTTP client per server lifespan."""

    @lifespan
    async def server_lifespan(server):
        http = (
            client_factory()
            if client_factory is not None
            else httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        )
        async with http:
            yield {"api_client": SmithsonianAPIClient(http)}

    return server_lifespan


def get_api_client(ctx: Context) -> SmithsonianAPIClient:
    return ctx.lifespan_context["api_client"]
