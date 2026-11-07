import sys
from pathlib import Path

EVALUATION = Path(__file__).resolve().parents[1]
API = EVALUATION.parent / "apps/api"
sys.path.insert(0, str(EVALUATION))
sys.path.insert(0, str(API))
