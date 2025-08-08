# Run with conda biomni_e1 env
# conda activate biomni_e1
import inspect
import importlib
import multiprocessing as mp
import pkgutil
import sys

from fastmcp import FastMCP

BASE_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
HOST = "0.0.0.0"          # expose to the network; change if you prefer

def serve(module_name: str, port: int) -> None:
    """Start one FastMCP server that exposes *all* public functions
    inside biomni.tool.<module_name>.
    """
    mod = importlib.import_module(f"biomni.tool.{module_name}")
    mcp = FastMCP(name=f"Biomni-{module_name}")

    registered = 0
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if name.startswith("_") or fn.__module__ != mod.__name__:
            continue
        try:
            mcp.tool(fn)
            registered += 1
            print(f"✓ [{module_name}] registered {name}")
        except Exception as exc:
            print(f"✗ [{module_name}] {name}: {exc}")

    print(f"[{module_name}] total tools registered: {registered}")
    mcp.run(transport="streamable-http", host=HOST, port=port)
    

def iter_tool_modules():
    """Yield every immediate child module in biomni.tool."""
    import biomni.tool as root
    for _loader, name, is_pkg in pkgutil.iter_modules(root.__path__):
        if not is_pkg:        # only plain .py modules
            yield name

def main():
    workers = []
    for i, module_name in enumerate(sorted(iter_tool_modules())):
        port = BASE_PORT + i
        p = mp.Process(target=serve, args=(module_name, port), daemon=False)
        p.start()
        workers.append((module_name, port, p))

    banner = "\n".join(
        f"http://{HOST}:{port}  →  biomni.tool.{mod}" for mod, port, _ in workers
    )
    print("=" * 60)
    print("Biomni MCP cluster running:")
    print(banner)
    print("=" * 60)

    # Wait for Ctrl-C
    try:
        for _, _, proc in workers:
            proc.join()
    except KeyboardInterrupt:
        print("\nShutting down…")
        for _, _, proc in workers:
            proc.terminate()

if __name__ == "__main__":
    main()
