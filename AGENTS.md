# Eliot development instructions

- Eliot is an autonomous cybersecurity agent with a Python/FastAPI runtime.
- The owner explicitly requires direct host execution. Do not add containers, virtual machines, or an execution-isolation layer.
- Preserve user-defined tool permissions, credential-to-endpoint binding, evidence provenance, cancellation and audit records.
- Use `review_and_roadmap.md` as the implementation checklist. Record actual validation and remaining live-integration requirements honestly.
- Run the Python and JavaScript suites before pushing. Never include credentials or local databases in commits.
