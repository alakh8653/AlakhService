# Security Policy

## Supported Versions

The following versions of AlakhService receive security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | ✅ Active support  |
| < 1.0   | ❌ End of life     |

---

## Reporting a Vulnerability

We take the security of AlakhService seriously. If you believe you have found a
security vulnerability, **please do not open a public GitHub issue**.

### Private Disclosure Process

1. **Email**: Send a detailed report to **security@alakhservice.com**  
   (PGP key available at https://alakhservice.com/.well-known/security.txt)

2. **GitHub Security Advisories**: Use
   [GitHub's private vulnerability reporting](https://github.com/AlakhService/AlakhService/security/advisories/new)
   — this is our preferred channel.

### What to Include

Please include as much of the following information as possible to help us
triage and reproduce the issue quickly:

- **Type of vulnerability** (e.g., SQL Injection, XSS, IDOR, RCE, privilege
  escalation, information disclosure, SSRF, etc.)
- **Affected component(s)** — service name, endpoint, or file path
- **Impact** — what an attacker could do if the vulnerability were exploited
- **Steps to reproduce** — a minimal proof-of-concept (PoC) or exploit script
- **Environment** — OS, runtime version, Docker image version, configuration
- **Suggested fix** (optional, but appreciated)

### Response Timeline

| Milestone                       | Target SLA          |
| ------------------------------- | ------------------- |
| Acknowledgement of report       | ≤ 48 hours          |
| Initial assessment & triage     | ≤ 5 business days   |
| Status update to reporter       | ≤ 10 business days  |
| Patch developed & reviewed      | ≤ 30 days (critical ≤ 7 days) |
| Public disclosure (coordinated) | After patch release |

We follow **Coordinated Vulnerability Disclosure (CVD)**. We ask that you:

- Allow us reasonable time to investigate and patch before public disclosure.
- Avoid accessing, modifying, or deleting data that is not yours.
- Avoid denial-of-service attacks or actions that degrade service availability.
- Act in good faith at all times.

---

## Security Measures

### Authentication & Authorisation

- All API endpoints (except public ones) require a valid JWT access token.
- Access tokens are short-lived (15 minutes). Refresh tokens are stored in
  `HttpOnly` secure cookies.
- Role-based access control (RBAC) is enforced at the API Gateway and within
  each service.
- Passwords are hashed with **bcrypt** (cost factor ≥ 12).
- Multi-factor authentication (TOTP/FIDO2) is available for all user accounts.

### Transport Security

- All production traffic is served over **TLS 1.2+**.
- HTTP Strict Transport Security (HSTS) is enforced with `max-age=31536000;
  includeSubDomains; preload`.
- Certificates are managed by Let's Encrypt via cert-manager.

### Secrets Management

- Secrets are **never** committed to source control.
- Production secrets are stored in AWS Secrets Manager / HashiCorp Vault.
- Docker and Kubernetes secrets are injected at runtime via environment
  variables or mounted volumes.
- The repository uses `gitleaks` and `detect-secrets` in CI to prevent
  accidental secret commits.

### Dependency Security

- Dependabot is enabled for automated dependency updates.
- All pull requests run `npm audit`, `pip-audit`, and Trivy container scans.
- SBOM (CycloneDX) is generated and published for every release.

### Container Security

- Docker images are built from minimal base images (distroless where possible).
- Images are scanned with **Trivy** and **Grype** on every CI build.
- Containers run as non-root users.
- Read-only root filesystems are enforced where possible.
- Network policies restrict pod-to-pod communication in Kubernetes.

### Code Security

- All PRs require a peer code review before merging.
- Static analysis (Bandit for Python, ESLint security plugin for TypeScript,
  CodeQL via GitHub Advanced Security) runs on every PR.
- OWASP ZAP DAST scans run against staging on every release.

### Database Security

- Database credentials are rotated every 90 days.
- All database connections use SSL/TLS.
- Row-Level Security (RLS) is enabled in PostgreSQL for multi-tenant data.
- Database backups are encrypted at rest.

---

## Incident Response

If a security incident is confirmed:

1. The security team will open a private GitHub Security Advisory.
2. A fix will be developed on a private branch and reviewed internally.
3. A patched release will be published with a CVE number (if applicable).
4. A public post-mortem will be published within 72 hours of resolution.

---

## Bug Bounty

We currently operate a **private responsible disclosure programme** and do not
offer monetary rewards. However, confirmed security researchers who responsibly
disclose valid vulnerabilities will be:

- Acknowledged in our `SECURITY-ACKNOWLEDGEMENTS.md` file.
- Listed in our public Hall of Fame (with their consent).

---

## Contact

- **Security email**: security@alakhservice.com
- **PGP fingerprint**: `ABCD 1234 EF56 7890 ABCD  1234 EF56 7890 ABCD 1234`
- **Security advisories**: https://github.com/AlakhService/AlakhService/security/advisories
- **Security.txt**: https://alakhservice.com/.well-known/security.txt

---

_This policy is inspired by
[Google's Vulnerability Reward Program rules](https://bughunters.google.com/about/rules/6625378258649088)
and the [CERT/CC Coordinated Vulnerability Disclosure guide](https://vuls.cert.org/confluence/display/CVD)._
