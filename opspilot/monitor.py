"""Configuration loading and HTTP endpoint checks."""

from dataclasses import dataclass
import json
import math
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Check:
    name: str
    url: str
    timeout_seconds: float = 5


@dataclass(frozen=True)
class CheckResult:
    name: str
    url: str
    healthy: bool
    status_code: int | None
    latency_ms: float
    error: str | None = None


def load_checks(config_path: str | Path) -> list[Check]:
    """Load and validate checks from a JSON configuration file."""
    try:
        with Path(config_path).open(encoding="utf-8") as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read configuration: {error}") from error

    if not isinstance(config, dict) or not isinstance(config.get("checks"), list):
        raise ValueError("configuration must contain a 'checks' array")
    if not config["checks"]:
        raise ValueError("'checks' must contain at least one endpoint")

    checks = []
    names = set()
    for index, item in enumerate(config["checks"], start=1):
        if not isinstance(item, dict):
            raise ValueError(f"check {index} must be an object")

        name = item.get("name")
        url = item.get("url")
        timeout = item.get("timeout_seconds", 5)
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"check {index} must have a non-empty name")
        if name in names:
            raise ValueError(f"check names must be unique: {name}")
        if not isinstance(url, str):
            raise ValueError(f"check '{name}' must have a URL")
        try:
            parsed_url = urlparse(url)
            host = parsed_url.hostname
            parsed_url.port
        except ValueError as error:
            raise ValueError(
                f"check '{name}' must use a valid http or https URL"
            ) from error
        if (
            parsed_url.scheme not in ("http", "https")
            or not parsed_url.netloc
            or not host
            or any(character.isspace() for character in url)
            or parsed_url.username is not None
            or parsed_url.password is not None
        ):
            raise ValueError(f"check '{name}' must use a valid http or https URL")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise ValueError(f"check '{name}' timeout_seconds must be a positive number")
        try:
            timeout = float(timeout)
        except OverflowError as error:
            raise ValueError(
                f"check '{name}' timeout_seconds must be a positive number"
            ) from error
        if not math.isfinite(timeout):
            raise ValueError(f"check '{name}' timeout_seconds must be a positive number")

        names.add(name)
        checks.append(Check(name=name, url=url, timeout_seconds=timeout))

    return checks


def check_endpoint(check: Check) -> CheckResult:
    """Make one GET request and return its health and elapsed time."""
    request = Request(check.url, headers={"User-Agent": "OpsPilot/0.1"})
    started_at = time.perf_counter()
    try:
        with urlopen(request, timeout=check.timeout_seconds) as response:
            status_code = response.getcode()
        latency_ms = (time.perf_counter() - started_at) * 1000
        healthy = 200 <= status_code < 300
        return CheckResult(
            name=check.name,
            url=check.url,
            healthy=healthy,
            status_code=status_code,
            latency_ms=latency_ms,
            error=None if healthy else f"HTTP {status_code}",
        )
    except HTTPError as error:
        latency_ms = (time.perf_counter() - started_at) * 1000
        error.close()
        return CheckResult(
            name=check.name,
            url=check.url,
            healthy=False,
            status_code=error.code,
            latency_ms=latency_ms,
            error=f"HTTP {error.code}",
        )
    except (URLError, TimeoutError, OSError) as error:
        latency_ms = (time.perf_counter() - started_at) * 1000
        reason = error.reason if isinstance(error, URLError) else error
        return CheckResult(
            name=check.name,
            url=check.url,
            healthy=False,
            status_code=None,
            latency_ms=latency_ms,
            error=str(reason),
        )
