# FastMCP Server Guidelines

These are the core conventions and patterns you should follow when building Python MCP servers with FastMCP.

---

## 1. Server Initialization  

References: [FastMCP Servers docs](https://gofastmcp.com/servers/fastmcp#initialization), [GitHub examples](https://github.com/jlowin/fastmcp/blob/main/examples/readme-quickstart.py)

```python
from fastmcp import FastMCP

mcp = FastMCP(
    name="MyServer",                  # Optional (recommended): human-readable identifier
    instructions="Describe usage...", # Optional (recommended): high‑level guidance for clients
    lifespan=startup_shutdown_mgr,    # optional async context manager
    tags={"analytics", "beta"}        # optional server tags
)
```

---

## 2. Core Components

References: [FastMCP Servers docs](https://gofastmcp.com/servers/fastmcp#components), [GitHub examples](https://github.com/jlowin/fastmcp/blob/main/examples/readme-quickstart.py)

1. **Tools**: functions clients invoke

```python
@mcp.tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b
```

Tool with context:
```python
@mcp.tool
def multiply(a: float, b: float, ctx: Context) -> float:
    """Multiply two numbers."""     # IMPORTANT: NEVER add "ctx" to the tool's docstring because this is a hidden parameter injected by the framework and should not be documented to the tool user

    # ... do something with ctx
    await ctx.info(f"Processing data from {data_uri}")
    return a * b
```


2. **Resources**: read‑only data endpoints

```python
@mcp.resource("config://settings")
def get_settings() -> dict:
    return {"mode": "prod"}
```
3. **Resource Templates**: parameterized URIs

```python
@mcp.resource("users://{user_id}/profile")
def user_profile(user_id: int) -> dict:
    return {"id": user_id}
```
4. **Prompts**: reusable LLM message builders

```python
@mcp.prompt()
def summarize(text: str) -> str:
    return f"Summarize:\n\n{text}"
```

---

## 3. Running & Transport

References: [FastMCP Servers docs](https://gofastmcp.com/servers/fastmcp#running), [GitHub examples](https://github.com/jlowin/fastmcp/blob/main/examples/streaming.py)

```python
if __name__ == "__main__":
    # STDIO (We use this for mostly for easy debugging)
    # mcp.run()

    # Streamable HTTP
    mcp.run(transport="http", host="127.0.0.1", port=9000)
```

---

## 4. Error Handling

References: [FastMCP Servers docs](https://gofastmcp.com/servers/fastmcp#error-handling)

* **Catch and wrap** exceptions within tools; raise clear, user‑friendly errors instead of raw tracebacks.
* **Log failures** (timeouts, validation, security) at WARN/ERROR level for diagnostics.
* **Handle external calls** safely:

```python
@mcp.tool
def fetch_data(url: str) -> dict:
    try:
        return httpx.get(url, timeout=5.0).json()
    except httpx.TimeoutException:
        raise RuntimeError("Upstream timed out—please try again later.")
    except Exception as e:
        mcp.log.error("fetch_data failed", exc_info=e)
        raise
```
* **Structured error payloads**: FastMCP marks `isError=true` and includes your message rather than crashing.

---

## 5. Composing & Mounting

References: [FastMCP Servers docs](https://gofastmcp.com/servers/fastmcp#composition), [GitHub examples](https://github.com/jlowin/fastmcp/blob/main/examples/mount_example.py)

You can split large apps into modular servers and link them:

```python
from fastmcp import FastMCP

main = FastMCP(name="Main")
sub  = FastMCP(name="Sub")

@sub.tool
def hello() -> str:
    return "hi"

# Live mount: updates in `sub` appear immediately in `main`
main.mount("sub", sub)

# Static import: snapshot of `sub` is copied into `main`
main.import_server("sub", sub)
```

---

## 6. Returning Images

References: [FastMCP Servers docs](https://gofastmcp.com/servers/fastmcp#images), [GitHub examples](https://github.com/jlowin/fastmcp/blob/main/examples/image_tool.py)

FastMCP provides first‑class support for image content via its `Image` helper class and by returning raw bytes with an explicit MIME type.

### As a Tool

```python
from fastmcp import FastMCP, Image
from PIL import Image as PILImage
import io

mcp = FastMCP("ImageDemo")

@mcp.tool
def generate_image(width: int, height: int, color: str) -> Image:
    """Generate a solid‑color PNG image."""
    img = PILImage.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Image(data=buf.getvalue(), format="png")
```

### As a Resource

```python
@mcp.resource(
    uri="images://logo",
    mime_type="image/png"
)
def get_logo() -> bytes:
    """Serve the company logo as PNG bytes."""
    with open("assets/logo.png", "rb") as f:
        return f.read()
```

---

## 7. Basic Data Structures & Classes

References: [FastMCP SDK source](https://github.com/jlowin/fastmcp/tree/main/fastmcp) for reference

* **`FastMCP`**: core server container
* **`ToolDefinition`**, **`ResourceDefinition`**, **`PromptDefinition`**: internal metadata
* **`Context`**: passed into async tools for logging, progress, sampling, and resource reads
* **`Image`**: helper class to wrap image bytes for clients


## 8. User & session

In the MCP session (HTTP session) we'll pass along the `session_id` and `user_id` as headers.
```
headers["session-id"] = session_id
headers["user-id"] = user_id
```

Assume that there is a function to get the user and session information from the headers:

```
def get_session_id_tuple(ctx: Context | None) -> tuple[str, str]:
    return get_user_id_from_request(ctx), get_session_id_from_request(ctx)
```

User and session information should be used to isolate data for each user and session.
We store data in a directory structure `DATA_DIR / user_id / session_id`, where `DATA_DIR` is a constant defined in the project (typically in `config.py`).

