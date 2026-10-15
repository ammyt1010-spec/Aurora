# Performance and release gate for AURORA Professional

- Composite indexes cover the most frequent response aggregation, study
  scoring, invitation and download-history access patterns.
- Additions are applied by Alembic revision 0016. Do not manually replace
  migrations. A full PostgreSQL migration is checked on every PR.
- npm dependencies are installed from the **committed** package-lock.json;
  `npm ci` fails if dependencies drift.
- Performance goals for launch must be established with anonymized synthetic
  datasets and a fixed database size. Passing unit tests does **not** certify
  a response-time, throughput or concurrency SLA.
- Analyze plans with `EXPLAIN (ANALYZE, BUFFERS)` in staging before adding
  more indexes. Indexes increase write overhead and storage.
- In production use compiled assets and a real application service rather
  than exposing Vite. Keep backups encrypted and rehearse restoration.
