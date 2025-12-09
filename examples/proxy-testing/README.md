# Prez Proxy Testing Examples

This directory contains Docker Compose setups for testing Prez behind different reverse proxies.

## Available Examples

- **Traefik** - `docker-compose.traefik.yml`
- **Nginx** - `docker-compose.nginx.yml` + `nginx.conf`
- **Apache** - `docker-compose.apache.yml` + `apache.conf`

Each example includes:
- The proxy server (Traefik/Nginx/Apache)
- Prez with in-memory Pyoxigraph
- Automated test container that validates proxy header handling

## Prerequisites

- Docker and Docker Compose
- Test data in `../../../../test_data` (relative to this directory)
  - Or modify the volume mount to point to your data directory

## Quick Start

### Traefik

```bash
# Start services (runs tests automatically)
docker compose -f docker-compose.traefik.yml up

# Or start services in background
docker compose -f docker-compose.traefik.yml up -d

# Run tests manually after services are up
docker compose -f docker-compose.traefik.yml run --rm test

# Clean up
docker compose -f docker-compose.traefik.yml down -v
```

Access:
- Prez API: http://localhost/api/prez/catalogs
- Traefik Dashboard: http://localhost:8080/dashboard/
- Swagger UI: http://localhost/api/prez/docs

### Nginx

```bash
# Start services (runs tests automatically)
docker compose -f docker-compose.nginx.yml up

# Or start services in background
docker compose -f docker-compose.nginx.yml up -d

# Run tests manually after services are up
docker compose -f docker-compose.nginx.yml run --rm test

# Clean up
docker compose -f docker-compose.nginx.yml down -v
```

Access:
- Prez API: http://localhost/api/prez/catalogs
- Swagger UI: http://localhost/api/prez/docs

### Apache

```bash
# Start services (runs tests automatically)
docker compose -f docker-compose.apache.yml up

# Or start services in background
docker compose -f docker-compose.apache.yml up -d

# Run tests manually after services are up
docker compose -f docker-compose.apache.yml run --rm test

# Clean up
docker compose -f docker-compose.apache.yml down -v
```

Access:
- Prez API: http://localhost/api/prez/catalogs
- Swagger UI: http://localhost/api/prez/docs

## What Gets Tested

Each test container validates:

1. **Basic proxy functionality** - Requests through the proxy work correctly
2. **Subpath routing** - Prez correctly responds at `/api/prez/*` paths
3. **API responses** - Catalog listings return expected RDF data

## Test Output

Successful tests show:
- API responses return RDF data (Turtle format by default)
- No 404 or 500 errors
- Services are healthy and responsive

## Configuration Details

All examples use:
- `ROOT_PATH=/api/prez` - Prez mounted at subpath
- `SPARQL_REPO_TYPE=pyoxigraph_memory` - In-memory triplestore

## Customization

### Change the Path Prefix

Edit both the compose file and proxy config:

**Traefik:**
```yaml
environment:
  ROOT_PATH: '/custom/path'
labels:
  - "traefik.http.routers.prez.rule=PathPrefix(`/custom/path`)"
```

**Nginx (`nginx.conf`):**
```nginx
location /custom/path/ {
    proxy_pass http://prez/custom/path/;
    ...
}
```

**Apache (`apache.conf`):**
```apache
ProxyPass /custom/path/ http://prez:8000/custom/path/
ProxyPassReverse /custom/path/ http://prez:8000/custom/path/
```

And update Prez:
```yaml
environment:
  ROOT_PATH: '/custom/path'
```

### Use Your Own Data

Change the volume mount in the compose file:
```yaml
volumes:
  - /path/to/your/data:/data:ro
```

### Test Without Subpath

Remove `ROOT_PATH` and adjust proxy rules to use `/` instead of `/api/prez`.

## Manual Testing

After starting services, test manually:

```bash
# Test basic request
curl http://localhost/api/prez/catalogs | jq '.'

# Test different profiles
curl http://localhost/api/prez/catalogs?_profile=mem | jq '.'

# Check OpenAPI spec
curl http://localhost/api/prez/docs/openapi.json | jq '.'
```

## Troubleshooting

### Test container fails immediately

Check that Prez is healthy:
```bash
docker compose -f docker-compose.traefik.yml ps
docker compose -f docker-compose.traefik.yml logs prez
```

### Links contain internal addresses

- Verify proxy is correctly forwarding requests to Prez
- Check that `ROOT_PATH` matches the proxy configuration

### 404 errors

- Ensure `ROOT_PATH` matches proxy path configuration
- Check proxy is passing the full path to Prez

### Can't access test data

Update the volume mount path in the compose file to point to existing test data.

## Reference

See [Running Prez Behind a Proxy](../../running_behind_proxy.md) for detailed documentation.
