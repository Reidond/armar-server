---
name: test-conventions
description: |
  Enforce testing conventions for the project backend. Covers the integration-first
  philosophy, timeout decorator requirements, DI-based mocking of all 3rd-party
  services, base class inheritance rules for endpoint tests, factory usage, and
  the banned patterns (performance tests, load tests, direct patch() calls).

  Use when: writing or reviewing test files, adding new test classes, choosing
  between unit and integration tests, setting up mocks for OpenAI / GCS / internal services,
  or troubleshooting test convention violations.
---
