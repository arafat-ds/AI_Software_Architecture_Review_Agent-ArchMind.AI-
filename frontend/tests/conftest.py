# Shared pytest fixtures for pipeline unit and integration tests.
#
# Add fixtures here:
#   - Mock HTTP responses for archmind_client.py (use respx for httpx mocking)
#   - Sample JobStatusResponse dicts (PENDING, RUNNING, COMPLETE, FAILED)
#   - Sample ReportResponse dict with metadata and sections[]
#   - Sample HealthResponse dict (all ok, degraded, unreachable)
#
# Import pattern from test files:
#   from pipelines.url_extractor import extract_repo_name
#   from pipelines.status_formatter import build_progress_checklist
#
# Run tests from frontend/ directory:
#   cd frontend && python -m pytest tests/
