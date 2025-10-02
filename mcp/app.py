from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Optional
import uvicorn
import os
import httpx

app = FastAPI(title="MCP (Model Context Protocol) Registry & Proxy")


class ServiceRecord(BaseModel):
    name: str
    url: str
    description: Optional[str] = None


# In-memory registry: name -> url
REGISTRY: Dict[str, ServiceRecord] = {}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/mcp/register")
async def register(rec: ServiceRecord):
    if not rec.name or not rec.url:
        raise HTTPException(status_code=400, detail="name and url required")
    REGISTRY[rec.name] = rec
    return {"registered": rec.name}


@app.get("/mcp/resolve/{name}")
async def resolve(name: str):
    rec = REGISTRY.get(name)
    if not rec:
        raise HTTPException(status_code=404, detail="service not found")
    return rec


@app.post("/mcp/invoke/{name}")
async def invoke(name: str, request: Request):
    """Proxy a JSON POST to a registered service. Returns service response.

    This is intentionally simple: it forwards headers and JSON body.
    """
    rec = REGISTRY.get(name)
    if not rec:
        raise HTTPException(status_code=404, detail="service not found")

    body = await request.json()
    timeout = float(os.getenv("MCP_INVOKE_TIMEOUT", "10"))
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(rec.url, json=body, headers={"X-Forwarded-By": "mcp"})
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=str(e))

    return {"status_code": resp.status_code, "body": resp.json() if resp.headers.get("content-type",""
                                                                     ).startswith("application/json") else resp.text}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9001")))
