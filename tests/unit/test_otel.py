"""app/core/otel.py (task 1.7) - disabled by default, and when configured, mirrors
app.core.tracing spans into OpenTelemetry. Guarded with importorskip since
opentelemetry-sdk is the optional 'otel' extra, not installed by a bare `uv sync`."""

import pytest

opentelemetry_sdk = pytest.importorskip("opentelemetry.sdk.trace")

from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode  # noqa: E402

from app.config import Settings  # noqa: E402
from app.core import otel  # noqa: E402
from app.core.tracing import Tracer  # noqa: E402


@pytest.fixture
def in_memory_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    otel.set_tracer_provider_for_testing(provider)
    yield exporter
    otel.reset_otel()


@pytest.mark.asyncio
async def test_disabled_by_default_exports_nothing():
    """The default, unconfigured state (no fixture - nothing has called
    set_tracer_provider_for_testing or init_otel with a real endpoint)."""
    assert otel.is_enabled() is False

    tracer = Tracer()
    async with tracer.start_span("some.span"):
        pass  # must not raise just because nothing is configured to receive it


def test_init_otel_is_a_noop_without_an_endpoint_configured():
    otel.reset_otel()
    otel.init_otel(Settings(otel_exporter_otlp_endpoint=""))
    assert otel.is_enabled() is False


def test_init_otel_wires_a_real_exporter_when_endpoint_is_configured():
    """Doesn't require a real OTLP collector listening - TracerProvider/
    BatchSpanProcessor/OTLPSpanExporter construction does no network I/O by itself,
    only actually exporting a span would. reset_otel() shuts down the
    BatchSpanProcessor's background worker thread afterward so it doesn't leak."""
    otel.reset_otel()
    try:
        otel.init_otel(Settings(otel_exporter_otlp_endpoint="http://localhost:4318"))
        assert otel.is_enabled() is True
    finally:
        otel.reset_otel()


@pytest.mark.asyncio
async def test_configured_exporter_captures_span_name_and_attributes(in_memory_exporter):
    assert otel.is_enabled() is True
    tracer = Tracer()

    async with tracer.start_span("gateway.generate", provider="groq", model="x") as span:
        span.attributes["extra"] = "value"

    spans = in_memory_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "gateway.generate"
    assert spans[0].attributes["provider"] == "groq"
    assert spans[0].attributes["model"] == "x"
    assert spans[0].attributes["extra"] == "value"
    assert spans[0].status.status_code == StatusCode.UNSET


@pytest.mark.asyncio
async def test_configured_exporter_marks_errored_spans(in_memory_exporter):
    tracer = Tracer()

    with pytest.raises(ValueError):
        async with tracer.start_span("failing.span"):
            raise ValueError("boom")

    spans = in_memory_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.ERROR
    assert "boom" in (spans[0].status.description or "")


class _BoomingTracer:
    def start_span(self, *_args, **_kwargs):
        raise RuntimeError("exporter is on fire")


@pytest.mark.asyncio
async def test_export_failure_never_breaks_the_request(in_memory_exporter, monkeypatch):
    """A broken exporter must not surface to the caller - exporting a span is
    diagnostic, never load-bearing for the request it describes."""
    monkeypatch.setattr(otel, "_otel_tracer", _BoomingTracer())

    tracer = Tracer()
    async with tracer.start_span("some.span"):
        pass  # must not raise, despite the broken exporter
