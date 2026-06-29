import sys
from pathlib import Path
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

import app.database as db_module
import app.main as main_module

_TEST_DB_PATH = Path(tempfile.gettempdir()) / f"test_vega_{os.getpid()}.db"
db_module.DATABASE_PATH = _TEST_DB_PATH
db_module.init_db()


def pytest_sessionfinish(session, exitstatus):
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
