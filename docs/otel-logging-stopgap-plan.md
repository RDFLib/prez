# OpenTelemetry-Aligned Logging Stopgap Plan

## 1. Objective

Refactor the work on `logging-overhaul` into a small, stable logging layer that is easy to connect to OpenTelemetry later, without implementing the OpenTelemetry SDK, tracing, metrics, exporters, or collector deployment now.

The stopgap will:

- Keep standard Python `logging` as the application-facing API.
- Emit readable console logs for humans and optionally newline-delimited JSON to stdout.
- Preserve structured values as typed `LogRecord` attributes instead of encoding and reparsing `event=... key=value` messages.
- Use names that can later become OpenTelemetry log attributes.
- Keep the current performance observations temporarily as structured logs.
- Establish one idempotent configuration boundary that can later install an OpenTelemetry `LoggingHandler`.
- Remove custom request-ID generation, propagation, and context handling.

The stopgap will not:

- Add OpenTelemetry dependencies.
- Create or export spans, metrics, or OTLP logs.
- Implement W3C Trace Context manually.
- Preserve compatibility with the branch's current logging format or fields.
- Preserve `X-Request-ID`; this branch has not been deployed and no compatibility requirement exists.
- Promise that timing logs are the permanent telemetry model. They are migration inputs for eventual spans and metrics.

## 2. Design decisions

### 2.1 Logging API

Application modules continue to use:

```python
log = get_logger(__name__)
```

`get_logger()` remains a thin wrapper around `logging.getLogger()`. It must not inject request IDs or parse messages. Returning a normal `logging.Logger` is preferred unless an adapter is needed for a concrete, documented reason.

Structured events use ordinary logging with flat, typed `extra` attributes:

```python
log.debug(
    "Listing query completed",
    extra={
        "event.name": "listing.query.complete",
        "prez.query.count": query_count,
        "duration_ms": duration_ms,
    },
)
```

Flat attributes are intentional: an eventual OpenTelemetry logging handler can copy custom `LogRecord` attributes directly. Do not put application attributes in a nested `structured_fields` dictionary.

A small `log_event()` helper is acceptable if it only sets `event.name` and forwards typed attributes to standard logging. It must not become an alternative logging framework.

### 2.2 Output

Logging writes to stdout only. Remove timestamped file creation and `LOG_OUTPUT`; production file rotation is out of scope and stdout is the cleanest future collector input.

Add:

- `LOG_LEVEL=DEBUG|INFO|WARNING|ERROR|CRITICAL`
- `LOG_FORMAT=console|json`

Defaults:

- `LOG_LEVEL=INFO`
- `LOG_FORMAT=console`

`console` is concise and optionally colored for humans. `json` emits exactly one JSON object per record with no text prefix, ANSI codes, or multiline wrapper. Exceptions may be represented as a string field in the JSON object.

Suggested JSON shape:

```json
{
  "timestamp": "2026-05-18T10:20:30.123Z",
  "severity_text": "INFO",
  "body": "Request completed",
  "logger.name": "prez.middleware",
  "attributes": {
    "event.name": "request.complete",
    "http.request.method": "GET",
    "http.response.status_code": 200,
    "url.path": "/catalogs",
    "duration_ms": 12.4
  },
  "resource": {
    "service.name": "prez",
    "service.version": "4.24.0"
  }
}
```

The exact JSON shape may change during eventual OTEL adoption; no compatibility guarantee is required. The important stopgap properties are typed attributes, one object per line, and separation of body, severity, logger, attributes, and resource identity.

### 2.3 Attribute conventions

Use these names where applicable:

| Meaning | Attribute |
|---|---|
| Event classification | `event.name` |
| Logger | `logger.name` |
| HTTP method | `http.request.method` |
| HTTP response status | `http.response.status_code` |
| Request path | `url.path` |
| Media type | `http.response.header.content-type` or a documented `prez.*` field |
| SPARQL query fingerprint | `prez.sparql.query_fingerprint` |
| Repository type | `prez.repository.type` |
| Cache result | `prez.cache.result` |
| RDF cardinality | `prez.rdf.quad_count` / `prez.rdf.triple_count` |

Continue using explicit units for temporary timing/size log attributes, such as `duration_ms`, `serialization_duration_ms`, and `response_size_bytes`. Domain-specific fields should generally use a `prez.*` namespace. Values must remain numbers or booleans rather than formatted strings.

Do not log raw authorization values, credentials, full SPARQL query text, or unbounded response bodies. Query fingerprints may be logged.

### 2.4 Request handling

Remove all of the following:

- `REQUEST_ID_HEADER`
- `NO_REQUEST_ID`
- Request ID `ContextVar`
- `new_request_id()`, bind/get/reset functions
- `RequestContextMiddleware`
- `X-Request-ID` response injection
- `X-Request-ID` forwarding to remote SPARQL endpoints
- Request-ID tests and documentation

Do not replace this with another custom correlation identifier. The eventual OTEL implementation will use incoming `traceparent` and active span context.

Keep `RequestTimingMiddleware` for the stopgap, including downstream/prez timing if it remains reliable. Its completion record must use typed extras and a useful body such as `"Request completed"`, not an empty message. Keep the downstream timing context separate from logging concerns, or clearly mark it as temporary telemetry debt.

### 2.5 Remaining application logs

Ordinary human messages do not all need event names. Startup, shutdown, configuration, warning, and error messages may remain normal logs.

Replace application-path `print()` calls with logging in:

- `prez/repositories/remote_sparql.py`
- `prez/renderers/renderer.py`
- `prez/services/app_service.py`
- `prez/services/connegp_service.py`

CLI-only messages for a missing Uvicorn installation and local Azure debugging may remain prints.

Use `log.exception()` when handling an active exception and a traceback is useful. Do not include an entire downstream response body in an exception/log without truncation and redaction.

## 3. Work delegation

The work is divided by file ownership to minimize merge conflicts. Each delegate should commit independently and include focused tests where practical.

### Delegate A — Logging contract and configuration

**Owns:**

- `prez/services/prez_logging.py`
- `prez/config.py`
- `.env-full-template`
- Logging configuration section of `README.md`

**Tasks:**

1. Simplify `get_logger()` so it no longer adds request context.
2. Remove key/value message parsing and nested `structured_fields` handling.
3. Implement console and newline-delimited JSON formatters over flat custom `LogRecord` attributes.
4. Ensure JSON preserves numeric, boolean, and null types.
5. Include UTC timestamp, severity, body, logger name, exception details, and service resource identity.
6. Make `setup_logger()` idempotent and prevent duplicate handlers when application factories or reloaders run repeatedly.
7. Replace `LOG_OUTPUT` with validated `LOG_FORMAT` and remove file logging/path creation.
8. Document that output has no compatibility guarantee and stdout is the supported destination.
9. Add focused formatter/configuration tests, but leave shared integration test reconciliation to Delegate E.

**Deliverable:** a documented logging contract that other delegates can code against.

### Delegate B — Remove request-ID implementation

**Owns:**

- Request-correlation portions of `prez/middleware.py`
- Middleware registration portions of `prez/app.py`
- Request-ID and forwarding portions of `prez/repositories/remote_sparql.py`

Because `prez/middleware.py` and `remote_sparql.py` also contain structured events, this delegate owns the complete stopgap migration of those two modules to avoid overlapping edits.

**Tasks:**

1. Delete the request-ID constants, context, helper functions, and middleware.
2. Remove `RequestContextMiddleware` registration.
3. Remove response header injection and downstream `X-Request-ID` forwarding.
4. Convert request completion and remote SPARQL timing events to the new flat typed attribute contract.
5. Keep query fingerprints and safe endpoint metadata.
6. Replace the remote SPARQL error `print()` with a bounded, structured error log; avoid leaking an unbounded response body.
7. Preserve downstream timing behavior until the eventual tracing migration.

**Deliverable:** request and SPARQL logging with no custom correlation mechanism.

### Delegate C — Convert performance event producers

**Owns:**

- `prez/renderers/renderer.py`
- `prez/routers/ogc_features_router.py`
- `prez/services/annotations.py`
- `prez/services/link_generation.py`
- `prez/services/listings.py`
- `prez/services/objects.py`

**Tasks:**

1. Replace every `event=... key=value` message with a human body and flat typed extras.
2. Replace nested `structured_fields` records with flat extras.
3. Apply the agreed attribute names and `prez.*` namespacing.
4. Preserve the existing measurement points and levels unless a measurement is clearly duplicate or incorrect.
5. Replace renderer application-path prints with logs.
6. Ensure potentially large RDF/SPARQL objects are not serialized into log messages.

**Deliverable:** all timing-heavy application modules emit typed records that can later flow through an OTEL logging handler.

### Delegate D — General logging cleanup and audit

**Owns:**

- Remaining Prez Python modules not owned by B or C
- `azure/function_app.py` review
- `main.py` review

**Tasks:**

1. Search for remaining `event=` strings, `structured_fields`, raw application-path `print()`, and direct `logging.getLogger()` usage inside `prez`.
2. Convert remaining structured events to the contract.
3. Replace appropriate prints in `app_service.py` and `connegp_service.py`.
4. Convert caught-exception logging to `log.exception()` where traceback context is valuable.
5. Audit debug logs for raw SPARQL queries, credentials, headers, and oversized values. Replace query text with a fingerprint or remove it.
6. Keep Uvicorn access logging disabled; `RequestTimingMiddleware` remains the stopgap request record.
7. Do not instrument Azure or Uvicorn with OTEL in this phase.

**Deliverable:** repository-wide logging hygiene report in the commit description and no known application-path stdout bypasses.

### Delegate E — Integration, tests, and final documentation

**Owns:**

- `tests/test_logging.py`
- Any new logging-focused test files
- Final edits to `README.md` and release-note wording after other delegates merge

**Tasks:**

1. Remove all request-ID tests.
2. Test console formatting without asserting unnecessary whitespace/color implementation details.
3. Test JSON output as parsed JSON, including typed numbers, booleans, nulls, exception text, and no ANSI/prefix text.
4. Test that ordinary messages containing `key=value` are not parsed.
5. Test idempotent setup and absence of duplicate records.
6. Test request completion fields and downstream/prez timing behavior.
7. Test that remote SPARQL requests no longer add `X-Request-ID`.
8. Run a repository-wide search for removed symbols and legacy event strings.
9. Reconcile documentation with the implemented settings and output.
10. Run the focused and full test suites and report unrelated pre-existing failures separately.

**Deliverable:** passing integration tests and final user-facing documentation.

## 4. Execution order

### Wave 0 — Contract agreement

The lead confirms:

- Flat `LogRecord` extras.
- Attribute naming table.
- JSON shape.
- `LOG_FORMAT` values and default.
- Stdout-only output.

No delegate should invent a second event representation.

### Wave 1 — Parallel foundation work

Run in parallel:

- Delegate A: logging contract/configuration.
- Delegate B: request-ID removal and request/SPARQL migration.

Delegate B codes to the agreed contract; it need not wait for Delegate A's implementation if the contract is fixed.

### Wave 2 — Parallel call-site migration

After Delegate A's interface is available, run in parallel:

- Delegate C: timing-heavy modules.
- Delegate D: remaining modules and security/print audit.

Delegate B's files remain excluded from both workstreams.

### Wave 3 — Integration

Delegate E rebases/merges all work, updates tests, resolves formatter expectations, and performs repository-wide checks.

### Wave 4 — Lead review

The lead reviews against the acceptance criteria, with particular attention to:

- No accidental request correlation implementation.
- No message reparsing.
- No duplicate handlers.
- No sensitive query/body logging.
- No claim that the stopgap is already OpenTelemetry.

## 5. Acceptance criteria

### Functional

- All Prez modules use standard Python logging through the centralized setup.
- No custom request ID is generated, returned, stored, or forwarded.
- No log formatter parses application message text for fields.
- Structured event attributes retain native types.
- `LOG_FORMAT=console` produces concise human-readable stdout.
- `LOG_FORMAT=json` produces one valid JSON object per line on stdout.
- Repeated logging setup does not duplicate handlers or output.
- Request completion, remote SPARQL, rendering, listing, annotations, and link generation observations remain available.
- Exceptions can include tracebacks without corrupting JSON output.

### Repository checks

These searches should return no application results, except documentation describing removed behavior where explicitly useful:

```bash
rg -n 'REQUEST_ID_HEADER|NO_REQUEST_ID|RequestContextMiddleware|get_request_id|bind_request_id|reset_request_id' prez tests
rg -n 'structured_fields' prez tests
rg -n 'event=[A-Za-z0-9_.-]+' prez --glob '*.py'
rg -n 'X-Request-ID' prez tests README.md
```

Review all remaining prints:

```bash
rg -n '\bprint\(' prez main.py azure --glob '*.py'
```

Only intentional CLI/local-debug prints should remain.

### Test commands

```bash
poetry run pytest tests/test_logging.py
poetry run pytest
poetry run black --check prez tests main.py azure
```

If lint tooling is added or already available in the execution environment, run it as well. Do not add unrelated formatting churn to this work.

## 6. Expected file impact

Likely modified:

- `.env-full-template`
- `README.md`
- `docs/2026-05-18-search-performance-release-notes.md`
- `prez/app.py`
- `prez/config.py`
- `prez/middleware.py`
- `prez/services/prez_logging.py`
- `prez/repositories/remote_sparql.py`
- Timing-heavy renderer, router, and service modules
- Modules containing application-path prints or unsafe debug logging
- `tests/test_logging.py`

No OpenTelemetry package or lockfile changes are expected in this stopgap.

Likely deleted behavior, but not necessarily deleted files:

- Request-ID context and middleware
- File logging
- Message-field parser
- Nested `structured_fields` transport

## 7. Risks and controls

| Risk | Control |
|---|---|
| A custom helper becomes another logging framework | Keep it thin and based on standard `logging`/`extra`; direct logging remains valid. |
| Event migration creates merge conflicts | Assign complete ownership of middleware and remote SPARQL to Delegate B; partition all other modules. |
| High-cardinality or sensitive values become attributes | Log route/path carefully, fingerprint queries, exclude credentials and headers, and bound error bodies. |
| JSON logs are tested too rigidly | Assert semantic fields and types, not key order or incidental whitespace. |
| Temporary duration logs become permanent pseudo-metrics | Document them as migration inputs and list their eventual span/metric destination. |
| Setup duplicates output under tests/reload | Make setup idempotent and test repeated calls. |
| Dot-named extras interact poorly with a future handler | Include a small proof test using ordinary `LogRecord.__dict__`; revisit only when the actual OTEL handler is introduced. |

## 8. Follow-on OTEL migration seam

The future implementation should be able to proceed without rewriting ordinary logs:

1. Add OpenTelemetry API/SDK and OTLP exporter dependencies.
2. Configure resource, tracer, meter, and logger providers inside the centralized setup boundary.
3. Add an OTEL `LoggingHandler` alongside or instead of the current stdout handler.
4. Instrument FastAPI and HTTPX to obtain W3C context propagation and trace/log correlation.
5. Convert temporary duration events into spans and metrics by operation family.
6. Remove downstream timing aggregation once traces provide the required breakdown.
7. Let the OTEL SDK attach `trace_id` and `span_id`; do not restore a custom request-ID layer.

This stopgap is complete when future work can replace handlers and migrate performance observations incrementally, rather than revisiting every ordinary logging call site.
