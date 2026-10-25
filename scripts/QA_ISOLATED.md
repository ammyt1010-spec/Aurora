# Isolated QA only

The capture, corporate acceptance, and security scripts require explicit test
configuration. They no longer assume a Windows machine, shared demo credentials,
a fixed project, or a public battery token. They must not target production.

Common environment variables:

- `AURORA_QA_ISOLATED=1`: explicit acknowledgement of a disposable test deployment.
- `AURORA_QA_OUTPUT_DIR`: local output directory (results contain no credentials).
- `AURORA_QA_FRONTEND_URL`: loopback frontend URL for browser scripts.
- `AURORA_QA_EMAIL`, `AURORA_QA_PASSWORD`: provisioned isolated account, supplied
  through the environment; no defaults and no demo-to-password fallback.
- `AURORA_QA_PROJECT_ID`: existing project owned by the browser test account.
- `AURORA_QA_BUNDLE_PUBLIC_ID`: existing isolated battery for full acceptance.
- `AURORA_QA_CHROME_PATH`: optional browser executable; otherwise Playwright's
  installed Chromium is used.

Security script:

- `AURORA_QA_API_URL`: loopback API base including `/api/v1`.
- For both `AURORA_QA_TENANT_A` and `AURORA_QA_TENANT_B`, supply suffixes `_EMAIL`,
  `_PASSWORD`, `_PROJECT_ID`, `_STUDY_ID`.
- Both users must own existing projects in **different organizations** and their
  studies must belong to those projects. The script verifies owner access first;
  a nonexistent resource is not evidence of tenant isolation. It verifies both
  cross-tenant directions and fails immediately on a failed assertion. The first
  account's newly created session is revoked in the logout test.
- Demo quotas are not tested by this script.

The corporate script checks every declared control; missing controls or preview
failures now fail the run rather than printing success. Its selectors must match
the version under test. It is not proof of successful acceptance until actually
run against an authorized fixture. Browser screenshots are visual evidence, not
proof of complete exports, signature validation, or survey submission.

Offline checks (no credentials, browser, server, or live services required):

```sh
python -m unittest discover -s scripts/tests -v
cd frontend && npm test -- src/pages/LoginPage.test.jsx
# From backend with its installed test environment:
python -m pytest -q app/tests/integration/test_qa_two_tenant_isolation.py app/tests/integration/test_study_instrument_immutability.py
```

Credential cleanup does not revoke secrets already exposed in Git history or
rotate existing accounts. Those are separate, explicitly authorized operations.
