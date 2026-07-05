#!/usr/bin/env python3
import asyncio
import json
import glob
import socket
import subprocess
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx
import uvicorn

app = FastAPI()
client = httpx.AsyncClient(timeout=30.0)
routing_table = {}          # skill_name -> local MCP endpoint URL
worker_processes = {}       # skill_name -> Popen (for cleanup)

def is_port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False

@app.on_event("startup")
async def startup():
    asyncio.create_task(scan_workers())

async def scan_workers():
    """Continuously scan workers/ directory for new registrations."""
    while True:
        for f in glob.glob("workers/*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    skill = data.get("skill")
                    url = data.get("url")
                    if not skill or not url:
                        continue
                    if skill in routing_table:
                        continue
                    # Find a free port starting from 6000
                    port = 6000
                    while not is_port_free(port):
                        port += 1
                    # Start Holesail client to connect to the worker
                    proc = subprocess.Popen(["holesail", url, "--port", str(port)])
                    worker_processes[skill] = proc
                    await asyncio.sleep(5)   # allow tunnel to establish
                    endpoint = f"http://localhost:{port}/mcp"
                    routing_table[skill] = endpoint
                    print(f"✅ Registered worker for '{skill}' at {endpoint}")
            except Exception as e:
                print(f"⚠️ Error scanning {f}: {e}")
        await asyncio.sleep(10)   # scan every 10 seconds

@app.post("/mcp")
async def mcp_gateway(request: Request):
    """Forward MCP tool calls to the appropriate worker."""
    body = await request.json()
    tool_name = body.get("tool", {}).get("name")
    if not tool_name:
        raise HTTPException(400, "Missing tool name")
    endpoint = routing_table.get(tool_name)
    if not endpoint:
        return JSONResponse({"error": f"Tool '{tool_name}' not found"}, status_code=404)
    try:
        resp = await client.post(f"{endpoint}/mcp", json=body)
        return JSONResponse(resp.json())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/routes")
async def list_routes():
    """Return the current routing table for debugging."""
    return routing_table

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
