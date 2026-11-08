"""Parts any pipeline can call. Importing this package puts apps/api and
evaluation/ on the import path, so `prod_*` wrappers can import the real app
code and toolkit files can reuse evaluation/scorers."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVALUATION = ROOT / "evaluation"
PLAYGROUND = EVALUATION / "playground"
API = ROOT / "apps/api"
for path in (API, EVALUATION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
