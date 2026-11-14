"""FastAPI application and scheduled endpoint monitoring."""

import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict
import math
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest

from opspilot.logging_config import logger
from opspilot.monitor import Check, CheckResult, check_endpoint, load_checks

DEFAULT_INTERVAL_SECONDS = 30


class MonitorService:
    def __init__(self, checks: list[Check]):
        self.checks = checks
        self.results: list[CheckResult] = []
        self._lock = asyncio.Lock()
        self.registry = CollectorRegistry()
        self._success = Gauge(
            "opspilot_check_success",
            "Whether the most recent endpoint check succeeded (1) or failed (0).",
            ["check_name"],
            registry=self.registry,
        )
        self._duration = Gauge(
            "opspilot_check_duration_seconds",
            "Duration of the most recent endpoint check in seconds.",
            ["check_name"],
            registry=self.registry,
        )
        self._last_checked = Gauge(
            "opspilot_last_check_timestamp_seconds",
            "Unix timestamp of the most recent endpoint check.",
            ["check_name"],
            registry=self.registry,
        )

    async def run_checks(self) -> list[CheckResult]:
        async with self._lock:
            results = await asyncio.gather(
                *(asyncio.to_thread(check_endpoint, check) for check in self.checks)
            )
            checked_at = time.time()
            for result in results:
                labels = {"check_name": result.name}
                self._success.labels(**labels).set(int(result.healthy))
                self._duration.labels(**labels).set(result.latency_ms / 1000)
                self._last_checked.labels(**labels).set(checked_at)
                logger.info(
                    "Endpoint check completed",
                    extra={
                        "event": "endpoint_check",
                        "check_name": result.name,
                        "healthy": result.healthy,
                        "status_code": result.status_code,
                        "latency_ms": round(result.latency_ms, 2),
                        "error": result.error,
                    },
                )
            self.results = results
            return results


async def _run_periodically(service: MonitorService, interval_seconds: float) -> None:
    while True:
        cycle_started = time.monotonic()
        await service.run_checks()
        remaining = interval_seconds - (time.monotonic() - cycle_started)
        await asyncio.sleep(max(0, remaining))


def _get_service(request: Request) -> MonitorService:
    service = getattr(request.app.state, "monitor", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Monitor is not ready")
    return service


def create_app(
    config_path: str | Path | None = None,
    interval_seconds: float | None = None,
) -> FastAPI:
    configured_path = config_path or os.getenv("OPSPILOT_CONFIG", "opspilot.json")
    configured_interval = (
        interval_seconds
        if interval_seconds is not None
        else float(os.getenv("OPSPILOT_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    )
    if (
        isinstance(configured_interval, bool)
        or not math.isfinite(configured_interval)
        or configured_interval <= 0
    ):
        raise ValueError("monitor interval must be a positive finite number")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        checks = load_checks(configured_path)
        service = MonitorService(checks)
        app.state.monitor = service
        monitor_task = asyncio.create_task(
            _run_periodically(service, configured_interval)
        )
        try:
            yield
        finally:
            monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await monitor_task

    app = FastAPI(
        title="OpsPilot",
        description="Read-only HTTP endpoint monitoring with Prometheus metrics.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs", status_code=307)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    @app.get("/healthz", tags=["health"])
    async def health():
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"])
    async def ready(request: Request):
        _get_service(request)
        return {"status": "ready"}

    @app.get("/api/v1/checks", tags=["monitoring"])
    async def list_checks(request: Request):
        service = _get_service(request)
        return {"checks": [asdict(check) for check in service.checks]}

    @app.get("/api/v1/results", tags=["monitoring"])
    async def get_results(request: Request):
        service = _get_service(request)
        results = service.results
        return {
            "healthy": bool(results) and all(result.healthy for result in results),
            "results": [asdict(result) for result in results],
        }

    @app.post("/api/v1/checks/run", tags=["monitoring"])
    async def run_checks(request: Request):
        service = _get_service(request)
        results = await service.run_checks()
        return {
            "healthy": all(result.healthy for result in results),
            "results": [asdict(result) for result in results],
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request):
        service = _get_service(request)
        return Response(
            content=generate_latest(service.registry),
            headers={"Content-Type": CONTENT_TYPE_LATEST},
        )

    return app


app = create_app()
