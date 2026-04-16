# Security Policy

## Supported versions

Only the latest release on the `main` branch receives security fixes.

| Version | Supported |
|---------|-----------|
| Latest (`main`) | Yes |
| Older releases | No |

## Reporting a vulnerability

If you find a security issue, **do not open a public issue**.

Instead, use GitHub's **private vulnerability reporting**:

1. Go to the [Security Advisories](https://github.com/Imbad0202/data-anonymizer/security/advisories) page.
2. Click **"Report a vulnerability"**.
3. Fill in the details — what you found, how to reproduce it, and the potential impact.

You will receive a response within 7 days. If the report is accepted, a fix will be issued and credited in the release notes. If declined, you will receive an explanation.

## Scope

Data Anonymizer handles personally identifiable information (PII). The following are in scope for security reports:

- **Anonymization bypass** — inputs or file formats that cause PII to pass through without being detected or masked
- **Data leakage** — scenarios where original (non-anonymized) data is written to disk, logs, or temp files unintentionally
- **Credential exposure** — build scripts or configurations that expose signing keys, API keys, or other secrets
- **Reverse mapping** — methods to recover original PII from anonymized output using information available in the application

The following are **out of scope**:

- False positives/negatives in NER detection — these are accuracy issues, not security vulnerabilities. Report them as regular issues.
- Feature requests or general bugs — use [Issues](https://github.com/Imbad0202/data-anonymizer/issues) instead
