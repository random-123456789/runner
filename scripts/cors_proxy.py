import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn
import asyncio

app = FastAPI()
TARGET_URL = "http://127.0.0.1:9119"

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request, path: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            url = f"{TARGET_URL}/{path}"
            # Pass all headers but ensure Host is specific
            headers = dict(request.headers)
            headers["Host"] = "127.0.0.1:9119"
            
            # Forward the request
            response = await client.request(
                method=request.method,
                url=url,
                params=request.query_params,
                headers=headers,
                content=await request.body()
            )
            return StreamingResponse(response.iter_raw(), status_code=response.status_code, headers=dict(response.headers))
        except httpx.ConnectError:
            # If dashboard is temporarily down, prevent 520 by waiting
            await asyncio.sleep(1)
            return {"error": "Dashboard warming up"}, 503

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9120)
