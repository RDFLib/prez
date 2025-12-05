# Running Prez Behind a Proxy

This guide explains how to configure Prez when running behind a reverse proxy (such as Traefik, Nginx, or cloud load balancers).

## Overview

When Prez runs behind a reverse proxy, it needs to respect forwarded headers to generate correct URLs in responses. This is critical for:
- Link generation in API responses
- OpenAPI/Swagger documentation
- Redirects and pagination

## Configuration

### Environment Variables

| Variable | Purpose | Example | Default |
|----------|---------|---------|---------|
| `PROXY_HEADERS` | Enable proxy header processing | `true` | `false` |
| `FORWARDED_ALLOW_IPS` | Trusted proxy IPs (comma-separated or `*` for all) | `10.0.0.1,172.16.0.0/12` | `127.0.0.1` |
| `ROOT_PATH` | Path prefix when Prez is mounted under a subpath | `/api/prez` | `` |
| `SYSTEM_URI` | Override base URI for link generation | `https://api.example.com` | Auto-detected |

### Minimal Configuration

For most reverse proxy setups:

```bash
PROXY_HEADERS=true
FORWARDED_ALLOW_IPS=*
```

**Security Note**: In production, set `FORWARDED_ALLOW_IPS` to your specific proxy IP addresses rather than `*`.

## Proxy Setup Examples

### Traefik

#### Docker Compose Example

```yaml
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.dashboard=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
    ports:
      - "80:80"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

  prez:
    image: ghcr.io/rdflib/prez:latest
    environment:
      PROXY_HEADERS: "true"
      FORWARDED_ALLOW_IPS: "*"
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.prez.rule=PathPrefix(`/`)"
      - "traefik.http.routers.prez.entrypoints=web"
      - "traefik.http.services.prez.loadbalancer.server.port=8000"
```

#### With Subpath

To mount Prez under a subpath (e.g., `/api/prez`):

```yaml
prez:
  environment:
    ROOT_PATH: "/api/prez"
    PROXY_HEADERS: "true"
    FORWARDED_ALLOW_IPS: "*"
  labels:
    - "traefik.http.routers.prez.rule=PathPrefix(`/api/prez`)"
    - "traefik.http.middlewares.prez-strip.stripprefix.prefixes=/api/prez"
    - "traefik.http.routers.prez.middlewares=prez-strip"
```

### Nginx

```nginx
upstream prez {
    server prez:8000;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://prez;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```

#### With Subpath

```nginx
location /api/prez/ {
    proxy_pass http://prez/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
}
```

Set `ROOT_PATH=/api/prez` in Prez environment.

### Azure API Management (APIM)

Azure APIM can rewrite URLs to add a path prefix that works with Prez's `ROOT_PATH` environment variable:

```xml
<policies>
    <inbound>
        <base />
        <set-backend-service base-url="https://your-prez-instance.azurecontainerapps.io" />
        <rewrite-uri template="@{
          // Get the path after APIM strips the API prefix
          var relativePath = context.Request.Url.Path;  // e.g., "/catalogs"
          return "/api/v1" + relativePath;
      }" copy-unmatched-params="true" />
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
```

Set Prez environment:
```bash
ROOT_PATH=/api/v1
PROXY_HEADERS=true
FORWARDED_ALLOW_IPS=*
```

The `rewrite-uri` policy prepends `/api/v1` to all requests before forwarding to Prez, allowing APIM to expose Prez at the root path while Prez operates under a subpath.

### Cloud Load Balancers

Most cloud providers (AWS ALB, GCP Load Balancer, Azure Application Gateway) automatically add `X-Forwarded-*` headers. Simply enable:

```bash
PROXY_HEADERS=true
FORWARDED_ALLOW_IPS=*  # Or your specific VPC CIDR
```

## Supported Headers

Prez recognizes the following proxy headers:

### X-Forwarded Headers (de facto standard)
- `X-Forwarded-Proto`: Original protocol (http/https)
- `X-Forwarded-Host`: Original host header
- `X-Forwarded-For`: Client IP chain

### RFC 7239 Forwarded Header
- `Forwarded`: Standard format (e.g., `for=192.0.2.60;proto=https;host=api.example.com`)

## Testing Your Setup

### Test Proxy Header Handling

```bash
# Test HTTPS forwarding
curl -H "X-Forwarded-Proto: https" http://localhost/catalogs | jq '.'

# Test custom domain
curl -H "X-Forwarded-Host: api.example.com" http://localhost/catalogs | jq '.'

# Test combined
curl -H "X-Forwarded-Proto: https" \
     -H "X-Forwarded-Host: api.mycompany.com" \
     http://localhost/catalogs | jq '.'
```

### Verify OpenAPI URLs

```bash
# Check server URLs in OpenAPI spec
curl http://localhost/docs/openapi.json | jq '.servers'
```

Expected output should reflect the forwarded protocol and host.

### Check Swagger UI

Visit `http://your-domain/docs` and verify:
- Page loads successfully
- API calls work correctly
- URLs don't reference internal container addresses

## Troubleshooting

### Links contain internal addresses (e.g., `http://prez:8000`)

**Cause**: `PROXY_HEADERS` not enabled or headers not being forwarded by proxy.

**Solution**:
1. Set `PROXY_HEADERS=true` in Prez
2. Verify proxy configuration includes forwarded headers
3. Check `FORWARDED_ALLOW_IPS` includes your proxy IP

### 401 Unauthorized or headers ignored

**Cause**: Proxy IP not in `FORWARDED_ALLOW_IPS`.

**Solution**: Add your proxy's IP to `FORWARDED_ALLOW_IPS` or use `*` for testing.

### Swagger UI fails to load

**Cause**: Incorrect URLs in OpenAPI spec.

**Solution**: 
1. Check `/docs/openapi.json` has correct server URLs
2. Ensure `ROOT_PATH` is set correctly if using subpath
3. Verify proxy passes all necessary headers

### HTTPS links when proxy uses HTTP (or vice versa)

**Cause**: Incorrect or missing `X-Forwarded-Proto` header.

**Solution**: Configure proxy to set `X-Forwarded-Proto` based on actual client connection protocol.

## Security Considerations

1. **Restrict trusted proxies**: Set `FORWARDED_ALLOW_IPS` to specific IP addresses in production
2. **Enable TLS**: Use HTTPS between client and proxy
3. **Validate headers**: Only trust headers from known proxies
4. **Internal communication**: Consider whether TLS is needed between proxy and Prez

## Advanced Configuration

### Using SYSTEM_URI

For complete control over generated URLs, set `SYSTEM_URI`:

```bash
SYSTEM_URI=https://api.example.com
```

This overrides auto-detection and uses the specified URI for all link generation.

### Multiple Proxy Layers

When using multiple proxies (e.g., CDN → Load Balancer → Prez):

```bash
FORWARDED_ALLOW_IPS=10.0.0.0/8,172.16.0.0/12
```

Ensure each proxy properly forwards or appends to `X-Forwarded-*` headers.

## Reference

- [Uvicorn Proxy Headers Documentation](https://www.uvicorn.org/settings/#http)
- [RFC 7239: Forwarded HTTP Extension](https://tools.ietf.org/html/rfc7239)
- [Link Generation Details](link_generation.md)

## Testing Setup

A complete Docker Compose setup for testing proxy configurations is available in the repository:

```bash
# Start test environment
docker compose -f docker-compose.traefik-test.yml up -d

# Run automated tests
./test-traefik-proxy.sh

# Clean up
docker compose -f docker-compose.traefik-test.yml down -v
```

See `docker-compose.traefik-test.yml` and `test-traefik-proxy.sh` for details.
