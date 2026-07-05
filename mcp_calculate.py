#!/usr/bin/env python3
from fastmcp import FastMCP

mcp = FastMCP("Calculator")

@mcp.tool()
def calculate(expr: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        return f"Result: {eval(expr)}"
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    mcp.run(host="0.0.0.0", port=50054)
