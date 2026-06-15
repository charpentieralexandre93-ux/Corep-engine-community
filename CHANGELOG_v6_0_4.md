# COREP Engine Community v6.0.4

## SBOM / SPDX corrective release

- reviewed runtime licence mappings now take precedence over environment-dependent package metadata;
- NumPy is deterministically emitted as `BSD-3-Clause`;
- `psycopg2-binary` is deterministically emitted as `LGPL-3.0-or-later`;
- compound SPDX values are serialized in CycloneDX `expression`, never in `license.id`;
- PEP 503 package-name normalization and idempotent enrichment are covered by regression tests;
- version metadata, CI/release guards and release artefacts are aligned to `6.0.4`.

No prudential formula, SQL mapping, engine API or public SA and SA-CCR scope boundary is changed.
