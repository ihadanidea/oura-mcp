import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from validate_fixtures import validate_fixtures  # noqa: E402


def test_fixtures_conform_to_openapi_spec():
    validate_fixtures()
