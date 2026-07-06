#!/usr/bin/env python3
"""
A generic MCP server that loads a GGUF model and exposes an inference tool
with a skill name. It can be used as a custom skill.
"""
import os
import json
import argparse
import asyncio
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False
    print("Warning: llama-cpp-python not installed. Install with: pip install llama-cpp-python")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill', required=True, help='Skill name (e.g., calculate)')
    parser.add_argument('--model', required=True, help='Path to GGUF model file')
    parser.add_argument('--port', type=int, default=50052, help='Port to listen on (ignored for stdio)')
    args = parser.parse_args()

    if not HAS_LLAMA:
        print("Error: llama-cpp-python is required.")
        sys.exit(1)

    llm = Llama(model_path=args.model, n_ctx=2048, n_threads=2, verbose=False)
    skill = args.skill

    server = Server(f"skill-{skill}")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=f"infer_{skill}",
                description=f"Run inference specialized for '{skill}' tasks.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                        "max_tokens": {"type": "integer", "default": 256},
                        "temperature": {"type": "number", "default": 0.7}
                    },
                    "required": ["prompt"]
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
        if not arguments:
            arguments = {}
        prompt = arguments.get("prompt", "")
        max_tokens = arguments.get("max_tokens", 256)
        temperature = arguments.get("temperature", 0.7)

        # Skill-specific prefix
        prefix = f"<|im_start|>system\nYou are an expert in {skill}. Provide accurate, helpful responses.\n<|im_end|>\n"
        full_prompt = prefix + prompt

        output = llm(full_prompt, max_tokens=max_tokens, temperature=temperature, echo=False)
        result = output["choices"][0]["text"]
        return [types.TextContent(type="text", text=result)]

    async def run():
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=f"skill-{skill}",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities()
                )
            )

    asyncio.run(run())

if __name__ == "__main__":
    import sys
    main()
