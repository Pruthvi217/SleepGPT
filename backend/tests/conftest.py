import os, sys, tempfile
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
_TMP = tempfile.mkdtemp(prefix="sleepgpt_test_")
os.environ["SLEEPGPT_ML_DB"] = os.path.join(_TMP, "ml.sqlite3")
os.environ["SLEEPGPT_SECRET_KEY"] = "test-secret-key"
os.environ["SLEEPGPT_ADMIN_USERNAME"] = "admin"
os.environ["SLEEPGPT_ADMIN_PASSWORD"] = "admin-test-pw"
for k in ("UBIDOTS_TOKEN", "SOMNNET_NORMALIZATION_MODE", "SOMNNET_TRAIN_MEAN", "SOMNNET_TRAIN_STD"):
    os.environ.pop(k, None)
from utils import storage  # isolate the JSON patient store
storage._DATA_DIR = _TMP
storage._PATIENTS_FILE = os.path.join(_TMP, "patients.json")
