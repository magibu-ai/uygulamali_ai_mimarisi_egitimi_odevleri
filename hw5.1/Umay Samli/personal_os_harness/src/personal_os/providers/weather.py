"""Provider-neutral weather records and an Open-Meteo read adapter."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

from personal_os.config import ExternalContextSettings


class WeatherProviderError(RuntimeError):
    """Raised when a weather provider cannot return a trustworthy result."""


@dataclass(frozen=True, slots=True)
class WeatherRequest:
    """Provider-neutral request for one location and calendar date."""

    location: str
    target_date: date


@dataclass(frozen=True, slots=True)
class ResolvedLocation:
    """The provider's location match, with enough detail to audit ambiguity."""

    name: str
    country: str | None
    latitude: float
    longitude: float
    timezone: str


@dataclass(frozen=True, slots=True)
class DailyForecast:
    """Normalized daily forecast fields used by planning conversations."""

    date: date
    weather_code: int | None
    temperature_max_c: float | None
    temperature_min_c: float | None
    precipitation_probability_max_percent: int | None
    sunrise: str | None
    sunset: str | None


@dataclass(frozen=True, slots=True)
class WeatherResult:
    """Auditable result that distinguishes unavailable forecasts from failures."""

    provider: str
    status: str
    requested_location: str
    target_date: date
    retrieved_at: datetime
    resolved_location: ResolvedLocation | None
    forecast: DailyForecast | None
    alerts: tuple[str, ...]
    uncertainty: str
    provenance_url: str


class WeatherProvider(Protocol):
    """Application seam for read-only weather lookup."""

    def get_weather(self, request: WeatherRequest) -> WeatherResult: ...


class JsonResponse(Protocol):
    headers: Mapping[str, str]

    def raise_for_status(self) -> None: ...

    def iter_content(self, chunk_size: int) -> Iterator[bytes]: ...

    def close(self) -> None: ...


class HttpSession(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, object],
        timeout: int,
        stream: bool,
    ) -> JsonResponse: ...


class OpenMeteoWeatherProvider:
    """Read-only Open-Meteo adapter with normalized, schema-checked results."""

    def __init__(
        self,
        settings: ExternalContextSettings,
        session: HttpSession | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._session: HttpSession = session or cast(HttpSession, requests.Session())
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_weather(self, request: WeatherRequest) -> WeatherResult:
        location = request.location.strip()
        if not location:
            raise WeatherProviderError("weather location cannot be empty")

        retrieved_at = self._clock()
        if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
            raise WeatherProviderError("weather provider clock returned an unaware datetime")
        resolved = self._resolve_location(location)
        try:
            local_today = retrieved_at.astimezone(ZoneInfo(resolved.timezone)).date()
        except ZoneInfoNotFoundError as error:
            raise WeatherProviderError("weather geocoding returned an invalid timezone") from error
        if request.target_date < local_today or request.target_date > local_today + timedelta(
            days=15
        ):
            return WeatherResult(
                provider="Open-Meteo",
                status="forecast_unavailable",
                requested_location=location,
                target_date=request.target_date,
                retrieved_at=retrieved_at,
                resolved_location=resolved,
                forecast=None,
                alerts=(),
                uncertainty=(
                    "The requested date is outside this adapter's supported 16-day forecast window."
                ),
                provenance_url=self._settings.weather_forecast_url,
            )
        forecast_body = self._get_json(
            self._settings.weather_forecast_url,
            {
                "latitude": resolved.latitude,
                "longitude": resolved.longitude,
                "timezone": resolved.timezone,
                "start_date": request.target_date.isoformat(),
                "end_date": request.target_date.isoformat(),
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max,sunrise,sunset"
                ),
            },
        )
        forecast = _parse_daily_forecast(forecast_body, request.target_date)
        status = "available" if forecast is not None else "forecast_unavailable"
        uncertainty = (
            "Provider forecast; conditions may change and no alert feed is available."
            if forecast is not None
            else (
                "The provider returned no forecast for the requested date, likely outside "
                "its horizon."
            )
        )
        return WeatherResult(
            provider="Open-Meteo",
            status=status,
            requested_location=location,
            target_date=request.target_date,
            retrieved_at=retrieved_at,
            resolved_location=resolved,
            forecast=forecast,
            alerts=(),
            uncertainty=uncertainty,
            provenance_url=self._settings.weather_forecast_url,
        )

    def _resolve_location(self, location: str) -> ResolvedLocation:
        body = self._get_json(
            self._settings.weather_geocoding_url,
            {"name": location, "count": 1, "language": "en", "format": "json"},
        )
        raw_results = body.get("results")
        if not isinstance(raw_results, list) or not raw_results:
            raise WeatherProviderError(f"weather location was not found: {location}")
        result_values = cast(list[object], raw_results)
        raw_match = result_values[0]
        if not isinstance(raw_match, dict):
            raise WeatherProviderError("weather geocoding returned an invalid location")
        match = cast(Mapping[str, object], raw_match)
        name = match.get("name")
        latitude = match.get("latitude")
        longitude = match.get("longitude")
        timezone_name = match.get("timezone")
        country = match.get("country")
        if (
            not isinstance(name, str)
            or not isinstance(latitude, int | float)
            or isinstance(latitude, bool)
            or not isinstance(longitude, int | float)
            or isinstance(longitude, bool)
            or not isinstance(timezone_name, str)
            or not -90 <= float(latitude) <= 90
            or not -180 <= float(longitude) <= 180
            or (country is not None and not isinstance(country, str))
        ):
            raise WeatherProviderError("weather geocoding returned an invalid location")
        return ResolvedLocation(
            name=name,
            country=country,
            latitude=float(latitude),
            longitude=float(longitude),
            timezone=timezone_name,
        )

    def _get_json(self, url: str, params: Mapping[str, object]) -> Mapping[str, object]:
        response: JsonResponse | None = None
        try:
            response = self._session.get(
                url,
                params=params,
                timeout=self._settings.timeout_seconds,
                stream=True,
            )
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length is not None and int(content_length) > (
                self._settings.maximum_response_bytes
            ):
                raise WeatherProviderError("weather provider response exceeds the size limit")
            raw = bytearray()
            for chunk in response.iter_content(chunk_size=16_384):
                if len(raw) + len(chunk) > self._settings.maximum_response_bytes:
                    raise WeatherProviderError("weather provider response exceeds the size limit")
                raw.extend(chunk)
            body = json.loads(raw)
        except requests.RequestException as error:
            raise WeatherProviderError("weather provider request failed") from error
        except (UnicodeDecodeError, ValueError) as error:
            raise WeatherProviderError("weather provider returned invalid JSON") from error
        finally:
            if response is not None:
                response.close()
        if not isinstance(body, dict):
            raise WeatherProviderError("weather provider returned a non-object response")
        return cast(Mapping[str, object], body)


def _parse_daily_forecast(body: Mapping[str, object], target_date: date) -> DailyForecast | None:
    raw_daily = body.get("daily")
    if not isinstance(raw_daily, dict):
        raise WeatherProviderError("weather provider response is missing daily forecast data")
    daily = cast(Mapping[str, object], raw_daily)
    dates = _list_field(daily, "time")
    target = target_date.isoformat()
    try:
        index = dates.index(target)
    except ValueError:
        return None
    return DailyForecast(
        date=target_date,
        weather_code=_optional_int_at(daily, "weather_code", index),
        temperature_max_c=_optional_float_at(daily, "temperature_2m_max", index),
        temperature_min_c=_optional_float_at(daily, "temperature_2m_min", index),
        precipitation_probability_max_percent=_optional_int_at(
            daily, "precipitation_probability_max", index
        ),
        sunrise=_optional_string_at(daily, "sunrise", index),
        sunset=_optional_string_at(daily, "sunset", index),
    )


def _list_field(values: Mapping[str, object], name: str) -> list[object]:
    value = values.get(name)
    if not isinstance(value, list):
        raise WeatherProviderError(f"weather provider response has invalid {name}")
    return cast(list[object], value)


def _value_at(values: Mapping[str, object], name: str, index: int) -> object:
    items = _list_field(values, name)
    if index >= len(items):
        raise WeatherProviderError(f"weather provider response has inconsistent {name}")
    return items[index]


def _optional_float_at(values: Mapping[str, object], name: str, index: int) -> float | None:
    value = _value_at(values, name, index)
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise WeatherProviderError(f"weather provider response has invalid {name}")
    return float(value)


def _optional_int_at(values: Mapping[str, object], name: str, index: int) -> int | None:
    value = _value_at(values, name, index)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise WeatherProviderError(f"weather provider response has invalid {name}")
    return value


def _optional_string_at(values: Mapping[str, object], name: str, index: int) -> str | None:
    value = _value_at(values, name, index)
    if value is None:
        return None
    if not isinstance(value, str):
        raise WeatherProviderError(f"weather provider response has invalid {name}")
    return value
