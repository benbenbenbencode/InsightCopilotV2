"""FastAPI wrapper.  Run:  uvicorn insightcopilot.api:app"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .adapters import AdapterError, publish_result
from .service import Service

app = FastAPI(title="InsightCopilot")


@lru_cache(maxsize=1)
def get_service() -> Service:
    return Service.build()


def require_key(x_api_key: Optional[str] = Header(default=None), svc: Service = Depends(get_service)):
    expected = svc.settings.api_key
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid API key")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    publish_to: Optional[Literal["metabase", "superset", "csv"]] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", dependencies=[Depends(require_key)])
def ask_endpoint(req: AskRequest, svc: Service = Depends(get_service)):
    result = svc.ask(req.question)
    if req.publish_to and result.ok and result.sql:
        try:
            result.chart_url = publish_result(result, req.publish_to)
        except AdapterError as e:
            result.warnings.append(f"Publish to {req.publish_to} failed: {e}")
    return result.to_dict()
