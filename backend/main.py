"""FastAPI application entry point for k8s-sentinel."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.k8s_client import init_k8s
from core.poller import start_poller, stop_poller
from routers import alerts, diagnosis, events, pods, resources, timeline

DEV_MODE = os.environ.get("DEV_MODE", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise k8s client and start background poller.
    Shutdown: stop the poller gracefully."""
    if not DEV_MODE:
        init_k8s()
    start_poller()
    yield
    stop_poller()


app = FastAPI(
    title="k8s-sentinel",
    description="AI-powered Kubernetes cluster health dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pods.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(resources.router, prefix="/api")
app.include_router(diagnosis.router, prefix="/api")
app.include_router(timeline.router, prefix="/api", tags=["timeline"])
app.include_router(alerts.router, prefix="/api")


@app.get("/healthz", tags=["health"])
async def healthz() -> dict:
    return {"status": "ok"}
