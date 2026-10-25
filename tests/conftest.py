import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("DEV_TOKEN_KEY", "test-only-dev-key-not-a-secret")
os.environ["MODEL_PROVIDER"] = "stub"
for k in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(k, None)  # tests always use the stub
