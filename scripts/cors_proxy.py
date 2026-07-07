import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI()
# Hermes dashboard is on 9119
TARGET_URL = "http://127.0.0.1:9119"

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request, path: str):
    async with httpx.AsyncClient() as client:
        url = f"{TARGET_URL}/{path}"
        # Strip restrictive headers that trigger security blocks
        headers = {k: v for k, v in request.headers.items() 
                   if k.lower() not in ["host", "origin", "referer", "sec-fetch-site"]}
        headers["Host"] = "127.0.0.1:9119"
        
        response = await client.request(
            method=request.method,
            url=url,
            params=request.query_params,
            headers=headers,
            content=await request.body()
        )
        return StreamingResponse(response.iter_raw(), status_code=response.status_code, headers=dict(response.headers))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9120)
