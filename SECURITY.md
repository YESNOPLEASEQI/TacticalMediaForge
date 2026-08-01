# Security Policy

MilitaryVideoGen is designed for trusted local use. It is not a hardened,
multi-tenant internet service.

## Safe defaults

- The desktop launchers bind the API and frontend to `127.0.0.1`.
- Docker publishes the API, SearXNG, and Crawl4AI ports on `127.0.0.1` only.
- Browser access is limited to the local frontend origins by default.
- Runtime credentials belong in `config.yaml` or environment variables. Never
  commit `.env`, `config.yaml`, databases, logs, generated media, or API keys.

## Before exposing a deployment

Place the application behind an authenticated reverse proxy, enable TLS, apply
request and spending limits, restrict outbound access, and keep the internal
API, SearXNG, Crawl4AI, and ComfyUI ports off the public network. The built-in
API does not provide user accounts or tenant isolation.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's security advisory
feature. Do not include live credentials or private generated content in a
public issue.
