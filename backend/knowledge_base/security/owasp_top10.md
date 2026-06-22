# OWASP Top 10 2021 — Risk Signals and Remediation

## A01: Broken Access Control

Access control enforces policy so that users cannot act outside of their intended permissions.
Failures result in unauthorised information disclosure, modification, or destruction of data.

Static signals: missing authorisation decorators, route handlers with no permission checks,
direct object references using user-supplied IDs without ownership verification.

Remediation:
- Deny access by default; grant permissions explicitly.
- Implement role-based access control (RBAC) at the service boundary.
- Validate ownership on every resource access — never trust client-supplied resource IDs alone.
- Log and alert on access control failures; rate-limit repeated failures.

## A02: Cryptographic Failures

Sensitive data exposed due to weak cryptography, missing encryption, or improper key management.

Static signals: hardcoded secrets or keys in source files, use of deprecated hash functions
(MD5, SHA1 for password storage), HTTP instead of HTTPS for sensitive endpoints,
symmetric key material embedded in configuration files.

Remediation:
- Never store secrets in source code. Use environment variables, secrets managers (Vault, AWS Secrets Manager).
- Use bcrypt, scrypt, or Argon2 for password hashing — never MD5 or SHA1.
- Enforce HTTPS for all endpoints that handle sensitive data.
- Rotate secrets regularly; implement key management lifecycle.

## A03: Injection

Untrusted data sent to an interpreter as part of a command or query. SQL, OS command,
LDAP, and template injection are all injection variants.

Static signals: string concatenation used to build SQL queries, f-string or format()
calls constructing OS commands, unsanitised user input passed to eval() or exec(),
raw query construction without parameterisation.

Remediation:
- Use parameterised queries / prepared statements for all database access.
- Use ORM query builders that parameterise by default.
- Never pass user input to shell commands; use subprocess with list arguments.
- Apply input validation at all system entry points — whitelist over blacklist.

## A04: Insecure Design

Design-level flaws that cannot be remediated by correct implementation alone.
Missing threat modelling, absent security requirements, no defence in depth.

Remediation:
- Conduct threat modelling during design (STRIDE, PASTA).
- Apply the principle of least privilege to all components and identities.
- Design for failure — assume breach; implement detection and response.

## A05: Security Misconfiguration

Insecure default configurations, verbose error messages, unnecessary features enabled,
missing security headers, default credentials unchanged.

Static signals: debug mode enabled in production configuration, verbose stack traces
returned to clients, permissive CORS policies (allow all origins), missing security headers.

Remediation:
- Disable debug mode and verbose errors in production.
- Implement Content Security Policy, HSTS, X-Frame-Options headers.
- Review and minimise CORS policy to known allowed origins only.
- Audit all default credentials and configuration values before deployment.

## A06: Vulnerable and Outdated Components

Using components with known vulnerabilities or no longer maintained dependencies.

Remediation:
- Audit dependencies with automated scanners (Safety, Snyk, Dependabot).
- Subscribe to security advisories for all major dependencies.
- Define and enforce a maximum acceptable dependency age policy.
- Pin dependency versions; review and test updates before promoting.

## A07: Identification and Authentication Failures

Weak authentication allowing credential stuffing, brute force, session hijacking.

Static signals: no rate limiting on authentication endpoints, long-lived sessions
without re-authentication for sensitive operations, session tokens in URLs.

Remediation:
- Implement rate limiting and account lockout on authentication endpoints.
- Use short-lived tokens with refresh token rotation.
- Require MFA for privileged operations.
- Invalidate sessions on logout and on privilege escalation.

## A08: Software and Data Integrity Failures

Assumptions about software integrity without verification. Insecure CI/CD pipelines,
deserialisation of untrusted data, auto-update without signature verification.

Remediation:
- Sign all artefacts in the CI/CD pipeline; verify signatures before deployment.
- Avoid deserialising untrusted data with pickle or Java serialisation.
- Pin all dependencies to verified digests in lock files.

## A09: Security Logging and Monitoring Failures

Missing or insufficient logging prevents detection and response.

Remediation:
- Log all authentication events, access control failures, and admin actions.
- Use structured logging with correlation IDs for cross-service tracing.
- Alert on anomalous patterns — repeated failures, unusual access volumes.
- Store logs in append-only storage outside the application's control.

## A10: Server-Side Request Forgery (SSRF)

Server fetches a URL supplied by the attacker, reaching internal infrastructure.

Static signals: URL fetching with user-controlled input, HTTP clients called with
parameters derived from user requests without validation.

Remediation:
- Validate and allowlist URLs before fetching — reject private IP ranges.
- Use a dedicated egress proxy that enforces allowlist policies.
- Disable HTTP redirects or validate redirect targets against the allowlist.
