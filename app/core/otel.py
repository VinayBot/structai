import logging
from typing import TYPE_CHECKING, Any

from app.config import Settings

if TYPE_CHECKING:
    from app.core.tracing import Span

logger = logging.getLogger(__name__)

# Deliberately not registered as OpenTelemetry's process-global TracerProvider
# (opentelemetry.trace.set_tracer_provider): StructAI has its own manual Tracer
# (app/core/tracing.py), not OTel auto-instrumentation, so nothing else needs to
# find this via OTel's global API. Keeping it local also avoids the global
# provider's "can only be set once per process" behavior, which would otherwise
# make this impossible to reconfigure cleanly across tests.
_otel_tracer: Any | None = None
# Tracked separately from _otel_tracer purely so reset_otel() can shut it down -
# a real provider's BatchSpanProcessor owns a background worker thread that
# otherwise outlives this module forgetting about it.
_provider: Any | None = None


def init_otel(settings: Settings) -> None:
    """No-op unless settings.otel_exporter_otlp_endpoint is set AND the optional
    'otel' extra is installed - disabled by default either way."""
    global _otel_tracer, _provider
    if not settings.otel_exporter_otlp_endpoint:
        return
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "OTEL_EXPORTER_OTLP_ENDPOINT is set but the 'otel' extra isn't installed - "
            "span export disabled. Install with `uv sync --extra otel`."
        )
        return

    provider = TracerProvider(resource=Resource.create({"service.name": "structai"}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
    )
    _provider = provider
    _otel_tracer = provider.get_tracer("structai")


def set_tracer_provider_for_testing(provider: Any) -> None:
    """Test hook: inject a TracerProvider directly (e.g. one wired to OTel's
    InMemorySpanExporter), bypassing the OTLP-endpoint-driven init_otel() above."""
    global _otel_tracer, _provider
    _provider = provider
    _otel_tracer = provider.get_tracer("structai")


def reset_otel() -> None:
    global _otel_tracer, _provider
    if _provider is not None:
        _provider.shutdown()
    _otel_tracer = None
    _provider = None


def is_enabled() -> bool:
    return _otel_tracer is not None


def export_span(span: "Span") -> None:
    """Mirrors a finished app.core.tracing.Span into OTel. A no-op whenever OTel
    isn't configured, and never raises on failure - exporting a span is diagnostic,
    it must never be able to break the request the span describes."""
    if _otel_tracer is None:
        return
    try:
        from opentelemetry.trace import Status, StatusCode

        start_ns = int(span.start_time * 1_000_000_000)
        end_time = span.end_time if span.end_time is not None else span.start_time
        end_ns = int(end_time * 1_000_000_000)

        otel_span = _otel_tracer.start_span(span.name, start_time=start_ns)
        for key, value in span.attributes.items():
            if value is None:
                continue
            if not isinstance(value, str | bool | int | float):
                value = str(value)
            otel_span.set_attribute(key, value)
        if span.status == "error":
            otel_span.set_status(Status(StatusCode.ERROR, span.error))
        otel_span.end(end_time=end_ns)
    except Exception:
        logger.warning("failed to export span to OpenTelemetry", exc_info=True)
