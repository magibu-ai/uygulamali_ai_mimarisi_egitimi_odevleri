from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime
from typing import cast

import pytest

from personal_os.config import ExternalContextSettings
from personal_os.providers.weather import (
    HttpSession as WeatherHttpSession,
)
from personal_os.providers.weather import (
    OpenMeteoWeatherProvider,
    WeatherProvider,
    WeatherProviderError,
    WeatherRequest,
    WeatherResult,
)
from personal_os.providers.web import (
    DirectHttpWebPageProvider,
    WebPageProvider,
    WebPageRequest,
    WebPageResult,
    WebProviderError,
)
from personal_os.providers.web import (
    HttpSession as WebHttpSession,
)
from personal_os.tools import Clock, ToolExecutionError, ToolRegistry, external_read_tools


def _settings(*, max_bytes: int = 1_000, max_characters: int = 1_000) -> ExternalContextSettings:
    return ExternalContextSettings(
        timeout_seconds=4,
        maximum_response_bytes=max_bytes,
        maximum_text_characters=max_characters,
        weather_geocoding_url="https://weather.example/geocode",
        weather_forecast_url="https://weather.example/forecast",
    )


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 14, 21, 30, tzinfo=UTC)


class WebStub:
    def __init__(self, result: WebPageResult | None = None) -> None:
        self.request: WebPageRequest | None = None
        self.result = result

    def fetch_page(self, request: WebPageRequest) -> WebPageResult:
        self.request = request
        if self.result is None:
            raise WebProviderError("page unavailable")
        return self.result


class WeatherStub:
    def __init__(self, result: WeatherResult | None = None) -> None:
        self.request: WeatherRequest | None = None
        self.result = result

    def get_weather(self, request: WeatherRequest) -> WeatherResult:
        self.request = request
        if self.result is None:
            raise WeatherProviderError("forecast unavailable")
        return self.result


def test_external_tools_expose_corrected_names_and_timezone_aware_date() -> None:
    registry = ToolRegistry(
        external_read_tools(
            cast(WebPageProvider, WebStub()),
            cast(WeatherProvider, WeatherStub()),
            default_timezone="Europe/Istanbul",
            clock=cast(Clock, FixedClock()),
        )
    )

    assert {definition.name for definition in registry.definitions} == {
        "time.get_current_date",
        "web.scrape_page",
        "weather.get_for_date",
    }
    assert registry.execute("time.get_current_date", {}) == {
        "source": "system_clock",
        "data": {
            "date": "2026-08-15",
            "timezone": "Europe/Istanbul",
            "retrieved_at": "2026-08-14T21:30:00+00:00",
        },
    }


def test_external_tool_provider_failures_become_recoverable_execution_errors() -> None:
    registry = ToolRegistry(
        external_read_tools(
            cast(WebPageProvider, WebStub()),
            cast(WeatherProvider, WeatherStub()),
            default_timezone="Europe/Istanbul",
        )
    )

    with pytest.raises(ToolExecutionError, match="page unavailable"):
        registry.execute("web.scrape_page", {"url": "https://example.com"})
    with pytest.raises(ToolExecutionError, match="forecast unavailable"):
        registry.execute("weather.get_for_date", {"location": "Istanbul", "date": "2026-08-15"})


class FakeJsonResponse:
    def __init__(self, body: object) -> None:
        self._body = json.dumps(body).encode()
        self.headers = {"content-length": str(len(self._body))}
        self.closed = False

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        yield self._body[:chunk_size]

    def close(self) -> None:
        self.closed = True


class WeatherSession:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, Mapping[str, object], int]] = []

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, object],
        timeout: int,
        stream: bool,
    ) -> FakeJsonResponse:
        assert stream is True
        self.calls.append((url, params, timeout))
        return FakeJsonResponse(self.responses.pop(0))


def test_open_meteo_adapter_normalizes_location_forecast_and_provenance() -> None:
    session = WeatherSession(
        [
            {
                "results": [
                    {
                        "name": "Istanbul",
                        "country": "Türkiye",
                        "latitude": 41.01,
                        "longitude": 28.97,
                        "timezone": "Europe/Istanbul",
                    }
                ]
            },
            {
                "daily": {
                    "time": ["2026-08-15"],
                    "weather_code": [1],
                    "temperature_2m_max": [29.5],
                    "temperature_2m_min": [21.0],
                    "precipitation_probability_max": [10],
                    "sunrise": ["2026-08-15T06:12"],
                    "sunset": ["2026-08-15T20:01"],
                }
            },
        ]
    )
    provider = OpenMeteoWeatherProvider(
        _settings(),
        session=cast(WeatherHttpSession, session),
        clock=lambda: datetime(2026, 8, 14, 12, tzinfo=UTC),
    )

    result = provider.get_weather(WeatherRequest("Istanbul", date(2026, 8, 15)))

    assert result.status == "available"
    assert result.resolved_location is not None
    assert result.resolved_location.timezone == "Europe/Istanbul"
    assert result.forecast is not None
    assert result.forecast.temperature_max_c == 29.5
    assert result.provenance_url == "https://weather.example/forecast"
    assert session.calls[1][1]["start_date"] == "2026-08-15"


def test_open_meteo_adapter_returns_unavailable_outside_forecast_horizon() -> None:
    session = WeatherSession(
        [
            {
                "results": [
                    {
                        "name": "Istanbul",
                        "country": "Türkiye",
                        "latitude": 41.01,
                        "longitude": 28.97,
                        "timezone": "Europe/Istanbul",
                    }
                ]
            }
        ]
    )
    provider = OpenMeteoWeatherProvider(
        _settings(),
        session=cast(WeatherHttpSession, session),
        clock=lambda: datetime(2026, 8, 14, 12, tzinfo=UTC),
    )

    result = provider.get_weather(WeatherRequest("Istanbul", date(2026, 9, 1)))

    assert result.status == "forecast_unavailable"
    assert result.forecast is None
    assert len(session.calls) == 1


class FakeStreamingResponse:
    status_code = 200

    def __init__(self, body: bytes, content_type: str = "text/html") -> None:
        self._body = body
        self.headers = {"content-type": content_type, "content-length": str(len(body))}
        self.closed = False

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        for index in range(0, len(self._body), chunk_size):
            yield self._body[index : index + chunk_size]

    def close(self) -> None:
        self.closed = True


class WebSession:
    def __init__(self, response: FakeStreamingResponse) -> None:
        self.response = response

    def get(
        self,
        url: str,
        *,
        timeout: int,
        stream: bool,
        allow_redirects: bool,
        headers: Mapping[str, str],
    ) -> FakeStreamingResponse:
        del url, timeout, stream, allow_redirects, headers
        return self.response


def test_direct_web_adapter_extracts_visible_bounded_text_and_rejects_private_hosts() -> None:
    response = FakeStreamingResponse(
        b"<html><head><title>Example</title><script>ignore me</script></head>"
        b"<body><h1>Hello</h1><p>Useful source text.</p></body></html>"
    )
    provider = DirectHttpWebPageProvider(
        _settings(max_characters=18),
        session=cast(WebHttpSession, WebSession(response)),
        resolver=lambda hostname, port: ("93.184.216.34",),
    )

    result = provider.fetch_page(WebPageRequest("https://example.com/article"))

    assert result.title == "Example"
    assert result.text == "Hello\nUseful sourc"
    assert result.truncated is True
    assert "Untrusted external source" in result.trust
    assert response.closed is True

    blocked = DirectHttpWebPageProvider(
        _settings(),
        session=cast(WebHttpSession, WebSession(response)),
        resolver=lambda hostname, port: ("127.0.0.1",),
    )
    with pytest.raises(WebProviderError, match="public"):
        blocked.fetch_page(WebPageRequest("http://internal.example/secrets"))
