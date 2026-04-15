"""HTTP 工具 - 发送 HTTP 请求。"""

import httpx

from backend.core.tools.base import register_tool


@register_tool(
    name="http_request",
    description="Make an HTTP request and return the response.",
    input_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to request",
            },
            "method": {
                "type": "string",
                "description": "HTTP method (GET, POST, PUT, DELETE)",
            },
            "headers": {
                "type": "object",
                "description": "Optional headers as key-value pairs",
            },
            "body": {
                "type": "string",
                "description": "Optional request body (for POST/PUT)",
            },
            "timeout": {
                "type": "integer",
                "description": "Request timeout in seconds (default: 30)",
            },
        },
        "required": ["url"],
    },
    permission="dangerous",
)
def http_request(arguments: dict) -> str:
    """
    Make an HTTP request and return the response.

    Args:
        url: The URL to request
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        headers: Optional headers as key-value pairs
        body: Optional request body (for POST/PUT)
        timeout: Request timeout in seconds
    """
    url = arguments["url"]
    method = arguments.get("method", "GET")
    headers = arguments.get("headers")
    body = arguments.get("body")
    timeout = arguments.get("timeout", 30)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(
                method=method.upper(),
                url=url,
                headers=headers or {},
                content=body,
            )

            result = f"Status: {response.status_code}\n"
            result += f"Headers: {dict(response.headers)}\n"
            result += f"Body:\n{response.text[:5000]}"  # 限制响应长度

            return result
    except httpx.TimeoutException:
        return f"Error: Request timed out after {timeout}s"
    except httpx.RequestError as e:
        return f"Error: Request failed - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"
