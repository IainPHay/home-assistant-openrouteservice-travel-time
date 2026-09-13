"""OpenRouteService HTTP client tests."""

from __future__ import annotations

import math
from typing import Any

from aiohttp import ClientError
import pytest

from custom_components.openrouteservice_travel_time.api import (
    OpenRouteServiceAuthenticationError,
    OpenRouteServiceClient,
    OpenRouteServiceConnectionError,
    OpenRouteServiceForbiddenError,
    OpenRouteServiceNoRouteError,
    OpenRouteServiceRateLimitError,
    OpenRouteServiceResponseError,
    _decode_json,
    _error_details,
    _number,
    _parse_route_result,
    _raise_for_error_response,
)
from custom_components.openrouteservice_travel_time.models import Coordinates


class FakeResponse:
    """Minimal aiohttp response context manager."""

    def __init__(self, status: int, text: str) -> None:
        self.status = status
        self._text = text

    async def text(self) -> str:
        """Return the configured response body."""
        return self._text

    async def __aenter__(self) -> "FakeResponse":
        """Enter the fake request context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the fake request context."""


class FakeSession:
    """Capture one POST and return a configured response."""

    def __init__(
        self,
        response: FakeResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.call: dict[str, Any] | None = None

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        """Capture the request."""
        self.call = {"url": url, **kwargs}
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


async def test_route_request_and_response_contract() -> None:
    """The client sends lon/lat coordinates and returns SI route values."""
    session = FakeSession(
        FakeResponse(
            200,
            '{"routes":[{"summary":{"distance":1234.5,"duration":678.9}}]}',
        )
    )
    client = OpenRouteServiceClient(session, "secret-key")  # type: ignore[arg-type]

    result = await client.async_route(
        Coordinates(55.1, -1.6),
        Coordinates(55.2, -1.5),
        "foot-walking",
    )

    assert result.duration_seconds == 678.9
    assert result.distance_metres == 1234.5
    assert session.call is not None
    assert session.call["url"].endswith("/directions/foot-walking")
    assert session.call["headers"]["Authorization"] == "secret-key"
    assert session.call["json"]["coordinates"] == [
        [-1.6, 55.1],
        [-1.5, 55.2],
    ]
    assert session.call["json"]["geometry"] is False
    assert session.call["json"]["instructions"] is False


async def test_route_network_error_is_classified() -> None:
    """aiohttp failures become a provider connection error."""
    client = OpenRouteServiceClient(  # type: ignore[arg-type]
        FakeSession(error=ClientError("offline")),
        "key",
    )

    with pytest.raises(OpenRouteServiceConnectionError):
        await client.async_route(
            Coordinates(55.1, -1.6),
            Coordinates(55.2, -1.5),
            "foot-walking",
        )


@pytest.mark.parametrize(
    ("status", "payload", "exception"),
    [
        (401, {"error": {"message": "Unauthorized"}}, OpenRouteServiceAuthenticationError),
        (403, {"error": {"message": "Invalid API key"}}, OpenRouteServiceAuthenticationError),
        (
            403,
            {"error": {"message": "Invalid API key or access to this API has been disallowed"}},
            OpenRouteServiceForbiddenError,
        ),
        (429, {"error": {"message": "Rate limit exceeded"}}, OpenRouteServiceRateLimitError),
        (404, {"error": {"message": "Not found"}}, OpenRouteServiceNoRouteError),
        (400, {"error": {"code": 2009, "message": "Route could not be found"}}, OpenRouteServiceNoRouteError),
        (500, {"error": {"message": "Server error"}}, OpenRouteServiceResponseError),
    ],
)
def test_http_error_classification(
    status: int,
    payload: object,
    exception: type[Exception],
) -> None:
    """Authentication, access, rate and routing failures stay distinct."""
    with pytest.raises(exception):
        _raise_for_error_response(status, payload)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"error": "plain error"}, (None, "plain error")),
        ({"error": {"code": 2009, "message": "no route"}}, (2009, "no route")),
        ({"detail": "detail text"}, (None, "detail text")),
        ({"title": "title text"}, (None, "title text")),
        ([], (None, "")),
    ],
)
def test_error_detail_extraction(
    payload: object, expected: tuple[int | None, str]
) -> None:
    """Known provider error envelopes are decoded defensively."""
    assert _error_details(payload) == expected


def test_invalid_json_is_rejected() -> None:
    """HTML or broken JSON never masquerades as route data."""
    with pytest.raises(OpenRouteServiceResponseError):
        _decode_json("<html>bad gateway</html>")


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"routes": []},
        {"routes": ["not-an-object"]},
        {"routes": [{}]},
        {"routes": [{"summary": "bad"}]},
    ],
)
def test_missing_route_data_is_rejected(payload: object) -> None:
    """Incomplete route payloads are unavailable rather than guessed."""
    with pytest.raises((OpenRouteServiceNoRouteError, OpenRouteServiceResponseError)):
        _parse_route_result(payload)


@pytest.mark.parametrize("value", [True, "1", -1, math.nan, math.inf])
def test_route_numbers_must_be_finite_non_negative(value: object) -> None:
    """Duration and distance values obey the Home Assistant entity contract."""
    with pytest.raises(OpenRouteServiceResponseError):
        _number(value, "duration")


def test_route_numbers_accept_ints() -> None:
    """Integer provider values are normalised to floats."""
    assert _number(42, "distance") == 42.0
