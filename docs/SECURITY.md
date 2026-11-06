# Security engineering — Mehrad Kavir AI

## Trust boundaries

- Customer messages and knowledge documents are untrusted data, not system instructions.
- Only approved knowledge and approved feedback rules enter AI context.
- Tokens, credentials and private session data are never added to AI prompts.
- Model output is a DRAFT, not an instruction to send. A logged-in editor or owner must explicitly approve each live message.
- For live replies the backend independently enforces Meta connection and time-window checks.
- The UI escapes untrusted HTML; CSP, no iframe embedding and no external JS dependencies.

## Access control

- Initial owner credentials generated with cryptographic randomness on first install.
- Passwords: salted scrypt. Sessions: opaque random tokens stored by SHA-256 hash.
- Cookies: HttpOnly, SameSite Strict, Secure when HTTPS is configured.
- Mutations: CSRF header checked against server session. User roles owner/editor/viewer.
- Login attempt throttling based on persistent audit records.
- Webhook requests: raw-body HMAC SHA-256 and account-ID comparison.
- Duplicate webhook events: unique event keys.

## Container defense

Non-root user, read-only container root, data volume only, dropped Linux capabilities,
no new privileges, host port bound to 127.0.0.1, health checks, data not committed to Git.

## Critical limitations

No system can be guaranteed impossible to bypass. This is a defense-in-depth MVP,
not a penetration-tested, enterprise-certified product.

Before exposing publicly, set up HTTPS reverse proxy, VPN/IP restriction, proxy
rate limiting, monitoring, automatic encrypted backups and recovery exercises.
For multi-node production, migrate SQLite to PostgreSQL and a distributed queue.

This version uses one manually configured Instagram token. OAuth onboarding,
token rotation, and continuous permission monitoring remain future work.

A network timeout during Meta send can be an uncertain delivery result;
inspect Instagram before manually retrying.

No autonomous outgoing Instagram replies are enabled in this version.
No PDF/video ingestion, OCR or continuous model fine-tuning is implemented.

## Incident response

1. Disable external sending by removing META_ACCESS_TOKEN from server environment.
2. Recreate containers; review security logs and audit trail.
3. Rotate affected tokens and credentials using the relevant provider.
4. Preserve evidence and backups. Notify affected customers where applicable.
5. Restore from a known-good backup and audit the cause before reconnecting.

## Threat coverage

Addressed: common prompt injection, unapproved-memory promotion, unauthorized
API mutations, webhook forgery, replay and accidental AI sends.
Not guaranteed: compromised host, leaked admin credentials, malicious privileged
administrator, denial of service, provider vulnerabilities and supply-chain attack.
