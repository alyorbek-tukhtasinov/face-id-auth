from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Testlar foydalanuvchining haqiqiy ma'lumotlariga tegmasligi uchun
_TMP = tempfile.mkdtemp(prefix="faceid-test-")
os.environ["FACEID_HOME"] = _TMP
os.environ["FACEID_NO_KEYRING"] = "1"

DATA = Path(__file__).parent / "data"


def models_available() -> bool:
    from faceid import models

    return not models.missing_models()


requires_models = pytest.mark.skipif(not models_available(), reason="modellar yuklanmagan (python -m faceid models)")


@pytest.fixture(scope="session")
def engine():
    if not models_available():
        pytest.skip("modellar yuklanmagan")
    from faceid.engine import Engine

    e = Engine()
    yield e
    e.close()
