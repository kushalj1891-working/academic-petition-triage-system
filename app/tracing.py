"""Optional OpenTelemetry OTLP export; workflow remains usable without a collector."""
import os
from functools import wraps

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace import Status, StatusCode
    _available=True
except Exception:
    trace=None; _available=False

def configure_tracing(service_name="petition-agent-worker"):
    if not _available: return
    provider=TracerProvider(resource=Resource.create({"service.name":service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT","http://jaeger:4317"),insecure=True)))
    trace.set_tracer_provider(provider)

def traced(name):
    def decorate(fn):
        @wraps(fn)
        def wrapped(state,*args,**kwargs):
            if not _available: return fn(state,*args,**kwargs)
            with trace.get_tracer("petition-triage").start_as_current_span(name,attributes={"run.id":state.get("run_id",""),"agent.step":name}) as span:
                try: return fn(state,*args,**kwargs)
                except Exception as exc:
                    span.record_exception(exc); span.set_status(Status(StatusCode.ERROR)); raise
        return wrapped
    return decorate
