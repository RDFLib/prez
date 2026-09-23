# OpenTelemetry-Aligned Logging Stopgap

## Objective

Provide useful structured request and performance logs now while keeping a clear migration path to proper OpenTelemetry tracing, metrics, and log export.

The stopgap:

- keeps standard Python `logging` as the application API;
- writes human-readable console logs or newline-delimited JSON to stdout;
- preserves structured values as flat, typed `LogRecord` attributes;
- records temporary request and performance observations;
- correlates each request by a Prez-generated ID and, when supplied, a separate client ID; and
- centralizes setup so an OpenTelemetry handler can be installed later.

It does not configure the OpenTelemetry SDK, create spans or metrics, export OTLP data, or implement W3C Trace Context manually.

## Logging contract

Application modules use ordinary loggers:

```python
log = get_logger(__name__)
log.debug(
    "Listing query completed",
    extra={
        "event.name": "listing.query.complete",
        "prez.query.count": query_count,
        "duration_ms": duration_ms,
    },
)
```

`get_logger()` remains a thin wrapper around `logging.getLogger()`. Structured values are supplied through flat `extra` attributes; messages are not parsed for `key=value` fields.

### Configuration

- `LOG_LEVEL=DEBUG|INFO|WARNING|ERROR|CRITICAL` (default `INFO`)
- `LOG_FORMAT=console|json` (default `console`)

Logs are written to stdout only. Setup is idempotent and owns one handler on the `prez` logger. JSON output separates timestamp, severity, body, logger name, application attributes, exception details, and service resource identity. The temporary output schema has no compatibility guarantee.

### Attribute conventions

| Meaning | Attribute |
|---|---|
| Event classification | `event.name` |
| HTTP method | `http.request.method` |
| HTTP response status | `http.response.status_code` |
| Request path | `url.path` |
| Prez request correlation | `prez.request.id` |
| Client request correlation | `prez.client_request.id` |
| SPARQL query fingerprint | `prez.sparql.query_fingerprint` |
| Repository type | `prez.repository.type` |
| Cache result | `prez.cache.result` |
| RDF cardinality | `prez.rdf.quad_count` / `prez.rdf.triple_count` |

Temporary timing and size attributes use explicit units, such as `duration_ms` and `response_size_bytes`. Values remain numbers, booleans, or null rather than formatted strings. Logs must not contain authorization values, credentials, complete SPARQL query text, or unbounded response bodies.

## Request correlation

Each HTTP request receives a random, opaque Prez request ID:

- returned in the `X-Request-ID` response header;
- attached to logs as `prez.request.id`; and
- never forwarded to remote SPARQL services.

A caller may send `X-Request-ID` for its own correlation. A client value is accepted only when there is exactly one header value and it consists of 1–128 safe ASCII characters (`A-Z`, `a-z`, digits, `.`, `_`, `:`, `/`, or `-`, beginning with an alphanumeric character). Accepted values are:

- attached separately as `prez.client_request.id`; and
- echoed in `X-Client-Request-ID`.

Invalid or repeated values are ignored rather than reflected. Keeping generated and client identifiers separate prevents callers from controlling Prez's own correlation namespace.

These IDs are application correlation values. They are **not** W3C trace IDs, are not stored in `trace_id` or `span_id`, and do not represent a distributed trace.

`RequestTimingMiddleware` emits one completion event per request with typed HTTP, response-size, and timing fields. Downstream wait aggregation remains temporary telemetry debt until spans provide the breakdown directly.

## Future OpenTelemetry direction

Proper distributed tracing should be introduced as one coherent change:

1. Add the OpenTelemetry API, SDK, OTLP exporter, and deployment configuration.
2. Configure resource, tracer, meter, and logger providers in the centralized telemetry setup boundary.
3. Instrument FastAPI and HTTPX rather than parsing or constructing `traceparent` in application middleware.
4. Extract an incoming W3C `traceparent`, or create a new root trace when it is absent or invalid.
5. Inject the active trace context into downstream HTTP calls.
6. Let OTEL populate native log-record `trace_id`, `span_id`, and trace flags.
7. Convert temporary duration events into spans and metrics and remove manual downstream timing aggregation.

A client that participates in distributed tracing will send a valid W3C header such as:

```http
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

An arbitrary business or request identifier must continue to use `X-Request-ID`; it must never be converted into a trace ID. Once OTEL is enabled, logs can be queried independently by native `trace_id`, `prez.request.id`, or `prez.client_request.id`.

## Acceptance criteria

- Every HTTP response has a generated `X-Request-ID`.
- An accepted client ID is logged separately and echoed as `X-Client-Request-ID`.
- Invalid client IDs are neither logged nor reflected.
- Active request IDs are attached to all records emitted through the configured Prez handler.
- IDs do not leak between concurrent or sequential requests.
- `X-Request-ID` is not forwarded to remote SPARQL services.
- Structured attribute types survive JSON formatting.
- Repeated logger setup does not duplicate handlers or records.
- No code manually parses or constructs W3C `traceparent`.
- Documentation does not present the stopgap as OpenTelemetry tracing.
