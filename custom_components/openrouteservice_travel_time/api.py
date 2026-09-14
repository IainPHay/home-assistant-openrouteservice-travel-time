"""Small asynchronous client for the hosted openrouteservice directions API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import logging
import math
from typing import cast

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_BASE_URL, REQUEST_TIMEOUT_SECONDS, VERSION
from .models import Coordinates, RouteResult

_LOGGER = logging.getLogger(__name__)
_NO_ROUTE_CODES = {2009, 2010, 2013, 2014, 2015, 2016, 2017}


class OpenRouteServiceError(Exception):
    """Base error raised by the provider client."""


class OpenRouteServiceConnectionError(OpenRouteServiceError):
    """The provider could not be reached."""


class OpenRouteServiceAuthenticationError(OpenRouteServiceError):
    """The provider explicitly rejected the API credential."""


class OpenRouteServiceForbiddenError(OpenRouteServiceError):
    """The provider denied access without proving the credential is invalid."""


class OpenRouteServiceRateLimitError(OpenRouteServiceError):
    """The provider rate limit was reached."""


class OpenRouteServiceNoRouteError(OpenRouteServiceError):
    """The provider could not calculate a route."""


class OpenRouteServiceResponseError(OpenRouteServiceError):
    """The provider returned an unexpected response."""


@dataclass(slots=True)
class OpenRouteServiceClient:
    """Direct HTTP client for the small API surface required by the integration."""

    session: ClientSession
    api_key: str
    base_url: str = API_BASE_URL

    async def async_route(
        self,
        origin: Coordinates,
        destination: Coordinates,
        profile: str,
    ) -> RouteResult:
        """Return route duration and distance."""
        url = f"{self.base_url}/directions/{profile}"
        headers = {
            "Accept": "application/json",
            "Authorization": self.api_key,
            "User-Agent": f"Home-Assistant-OpenRouteService-Travel-Time/{VERSION}",
        }
        body = {
            "coordinates": [origin.ors_pair, destination.ors_pair],
            "geometry": False,
            "instructions": False,
        }

        try:
            async with self.session.post(
                url,
                headers=headers,
                json=body,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
            ) as response:
                text = await response.text()
                if response.status >= 400:
                    _raise_for_error_response(
                        response.status,
                        _decode_error_json(text),
                    )
                payload = _decode_json(text)
        except (ClientError, TimeoutError) as err:
            _LOGGER.warning(
                "OpenRouteService request failed (%s): %s",
                type(err).__name__,
                err,
            )
            raise OpenRouteServiceConnectionError(
                "Unable to communicate with openrouteservice"
            ) from err

        return _parse_route_result(payload)


def _decode_json(text: str) -> object:
    """Decode provider JSON without trusting its schema."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise OpenRouteServiceResponseError(
            "openrouteservice returned invalid JSON"
        ) from err


def _decode_error_json(text: str) -> object:
    """Decode an error body, tolerating non-JSON proxy/provider failures."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _error_details(payload: object) -> tuple[int | None, str]:
    """Extract the internal ORS error code and a human-readable message."""
    if not isinstance(payload, Mapping):
        return None, ""
    data = cast(Mapping[str, object], payload)
    error = data.get("error")
    if isinstance(error, str):
        return None, error
    if isinstance(error, Mapping):
        error_map = cast(Mapping[str, object], error)
        code = error_map.get("code")
        message = error_map.get("message")
        return (
            int(code) if isinstance(code, int) and not isinstance(code, bool) else None,
            str(message) if isinstance(message, str) else "",
        )
    detail = data.get("detail")
    title = data.get("title")
    message = detail if isinstance(detail, str) else title
    return None, str(message) if isinstance(message, str) else ""


def _explicit_invalid_api_key(message: str) -> bool:
    """Return true only for an unambiguous invalid-key provider message."""
    normalised = " ".join(message.casefold().split())
    if "invalid api key" not in normalised:
        return False
    return " or " not in normalised and "access" not in normalised


def _raise_for_error_response(status: int, payload: object) -> None:
    """Classify provider errors without treating every 403 as bad credentials."""
    code, message = _error_details(payload)
    detail = message or f"openrouteservice returned HTTP {status}"

    if code in _NO_ROUTE_CODES:
        raise OpenRouteServiceNoRouteError(detail)
    if status == 401:
        raise OpenRouteServiceAuthenticationError(detail)
    if status == 403:
        if _explicit_invalid_api_key(message):
            raise OpenRouteServiceAuthenticationError(detail)
        raise OpenRouteServiceForbiddenError(detail)
    if status == 429:
        raise OpenRouteServiceRateLimitError(detail)
    if status == 404:
        raise OpenRouteServiceNoRouteError(detail)
    raise OpenRouteServiceResponseError(detail)


def _number(value: object, field: str) -> float:
    """Return one finite non-negative number from a provider response."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenRouteServiceResponseError(f"Route {field} is not numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise OpenRouteServiceResponseError(f"Route {field} is invalid")
    return result


def _parse_route_result(payload: object) -> RouteResult:
    """Extract the JSON route summary documented by openrouteservice."""
    if not isinstance(payload, Mapping):
        raise OpenRouteServiceResponseError("Route response is not an object")
    data = cast(Mapping[str, object], payload)
    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        raise OpenRouteServiceNoRouteError("openrouteservice returned no routes")
    route = routes[0]
    if not isinstance(route, Mapping):
        raise OpenRouteServiceResponseError("Route entry is not an object")
    route_map = cast(Mapping[str, object], route)
    summary = route_map.get("summary")
    if not isinstance(summary, Mapping):
        raise OpenRouteServiceResponseError("Route summary is missing")
    summary_map = cast(Mapping[str, object], summary)
    return RouteResult(
        duration_seconds=_number(summary_map.get("duration"), "duration"),
        distance_metres=_number(summary_map.get("distance"), "distance"),
    )
