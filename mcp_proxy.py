import asyncio
import json
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx
import uvicorn
import glob
import time

app = FastAPI()
client = httpx.AsyncClient(timeout=30.0)
routing_table = {}  # skill_name -> local MCP endpoint URL

@app.on_event("startup")
async def startup():
    # Periodically scan the workers/ directory for new registrations
    asyncio.create_task(scan_workers())

async def scan_workers():
    while True:
        # Look for .json files in workers/
        for f in glob.glob("workers/*.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    skill = data.get("skill")
                    url = data.get("url")
                    if skill and url and skill not in routing_table:
                        # Assign a local port for this worker
                        port = 6000
                        while True:
                            # Check if port is free
                            import socket
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            try:
                                s.bind(("127.0.0.1", port))
                                s.close()
                                break
                            except OSError:
                                port += 1
                        # Start Holesail client to connect to the worker
                        # We use subprocess to run holesail in background
                        import subprocess
                        subprocess.Popen(["holesail", url, "--port", str(port)])
                        # Wait a moment for tunnel
                        await asyncio.sleep(5)
                        # Register with proxy
                        endpoint = f"http://localhost:{port}/mcp"
                        routing_table[skill] = endpoint
                        print(f"✅ Added route: {skill} -> {endpoint}")
            except Exception as e:
                print(f"⚠️ Error scanning {f}: {e}")
        await asyncio.sleep(10)  # scan every 10 seconds

@app.post("/add_route")
async def add_route(request: Request):
    data = await request.json()
    skill = data.get("skill")
    endpoint = data.get("endpoint")
    if not skill or not endpoint:
        raise HTTPException(400, "Missing skill or endpoint")
    routing_table[skill] = endpoint
    return {"status": "ok"}

@app.post("/remove_route")
async def remove_route(request: Request):
    data = await request.json()
    skill = data.get("skill")
    if skill in routing_table:
        del routing_table[skill]
    return {"status": "ok"}

@app.post("/mcp")
async def mcp_gateway(request: Request):
    body = await request.json()
    # Assume MCP request contains "tool" field with "name"
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
    return routing_table

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
