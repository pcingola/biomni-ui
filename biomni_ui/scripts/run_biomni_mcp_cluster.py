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

def read_module2api(field: str) -> list[dict]:
    """
    Given a short field name like 'biochemistry', load:
      biomni.tool.tool_description.<field>
    and return its 'description' list.
    """
    module_name: str = f"biomni.tool.tool_description.{field}"
    module = importlib.import_module(module_name)
    return module.description  # list of tool schemas

def serve(module_name: str, port: int) -> None:
    """Start one FastMCP server that exposes *all* public functions
    inside biomni.tool.<module_name>.
    """
    mod = importlib.import_module(f"biomni.tool.{module_name}")
    mcp = FastMCP(name=f"Biomni-{module_name}")
    api_schemas = read_module2api(module_name)

    registered = 0
    for tool_schema in api_schemas:
        name = tool_schema.get('name')
        description = tool_schema.get('description', 'No description available')
        required_names = "\n".join([p['name'] for p in tool_schema.get("required_parameters", [])])
        optional_names = "\n".join([p['name'] for p in tool_schema.get("optional_parameters", [])])
        full_description = f"{description}\n(Required parameters:\n{required_names}\nOptional parameters:\n{optional_names})"

        fn = getattr(mod, tool_schema['name'], None)
        try:
            mcp.tool(fn, name=name, description=full_description, tags=set(["biomni", module_name]))
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
        
        if module_name == "tool_registry":
            continue
        
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
