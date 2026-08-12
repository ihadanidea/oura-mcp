"""Validate tests/fixtures/*.json `data[]` entries against the vendored Oura
OpenAPI spec, so fixture drift from the real API shape fails loudly.

Run directly:  uv run python scripts/validate_fixtures.py
Also imported by tests/test_fixtures_validate.py.
"""

import json
import warnings
from pathlib import Path

import jsonschema

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
SPEC_PATH = FIXTURES_DIR / "openapi-1.37.json"

# fixture file stem -> OpenAPI component schema name for one `data[]` record
FIXTURE_SCHEMAS = {
    "daily_activity": "PublicDailyActivity",
    "daily_readiness": "PublicDailyReadiness",
    "daily_sleep": "PublicDailySleep",
    "sleep_page1": "PublicModifiedSleepModel",
    "sleep_page2": "PublicModifiedSleepModel",
    "workout": "PublicWorkout",
    "session": "PublicSession",
    "daily_stress": "PublicDailyStress",
    "daily_spo2": "PublicDailySpO2",
    "enhanced_tag": "EnhancedTagModel",
    "heartrate": "PublicHeartRateRow",
}


def validate_fixtures() -> None:
    spec = json.loads(SPEC_PATH.read_text())
    with warnings.catch_warnings():
        # jsonschema's replacement (the `referencing` library) is more code
        # than this one-off validator warrants; RefResolver still works.
        warnings.simplefilter("ignore", DeprecationWarning)
        resolver = jsonschema.RefResolver.from_schema(spec)
    schemas = spec["components"]["schemas"]

    for stem, schema_name in FIXTURE_SCHEMAS.items():
        fixture_path = FIXTURES_DIR / f"{stem}.json"
        fixture = json.loads(fixture_path.read_text())
        schema = schemas[schema_name]
        validator = jsonschema.Draft7Validator(schema, resolver=resolver)
        for record in fixture["data"]:
            errors = sorted(validator.iter_errors(record), key=str)
            if errors:
                detail = "; ".join(
                    f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors
                )
                raise AssertionError(
                    f"{fixture_path.name} record {record.get('id', '?')} "
                    f"fails schema {schema_name}: {detail}"
                )


if __name__ == "__main__":
    validate_fixtures()
    print(f"All {len(FIXTURE_SCHEMAS)} fixtures valid against {SPEC_PATH.name}.")
