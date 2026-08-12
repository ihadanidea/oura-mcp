# Test fixtures

All JSON files in this directory are **synthetic** — no real Oura account,
device, or health data was used to produce them. Field names and shapes were
cross-checked against Oura's public API v2 OpenAPI spec, vendored here as
`openapi-1.37.json` (fetched from
`https://cloud.ouraring.com/v2/static/json/openapi-1.37.json`) so fixture
validation (`scripts/validate_fixtures.py`) runs offline.

- `sleep_page1.json` / `sleep_page2.json` are a deliberate pagination pair:
  page 1 carries a `next_token`, page 2 has `next_token: null`. This is what
  the pagination test (`test_client.py`) and the multi-page integration
  scenario hang on.
- Every other file is a single-page `{"data": [...], "next_token": null}`
  response for its endpoint.
