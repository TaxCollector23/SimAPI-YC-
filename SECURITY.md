# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities. Email
`security@simapi.dev` with a description, reproduction steps, and impact. We aim
to acknowledge within 48 hours and to ship a fix or mitigation within 7 days for
high-severity issues.

## Handling secrets

- No secrets are committed to this repository. All credentials are read from the
  environment (see [`.env.example`](.env.example)).
- CI runs [gitleaks](https://github.com/gitleaks/gitleaks) on every push and PR
  to block accidental secret commits.
- A `detect-private-key` pre-commit hook runs locally.

> **Note:** The pre-1.0 history of this project contained a hardcoded OpenRouter
> API key. It has been removed and must be treated as compromised — **rotate that
> key** if it was ever live.

## Supported versions

| Version | Supported |
| ------- | --------- |
| 3.1.x   | ✅        |
| < 3.1   | ❌        |

## Hardening checklist for production

- Set `SIMAPI_REQUIRE_AUTH=true` and provision `SIMAPI_API_KEYS`.
- Restrict `SIMAPI_CORS_ORIGINS` to known front-end origins.
- Terminate TLS at your load balancer / ingress.
- Keep `SIMAPI_LOG_JSON=true` and ship logs to a central store.
- Run behind the built-in rate limiter (or a shared Redis-backed limiter for
  multi-replica deployments).
