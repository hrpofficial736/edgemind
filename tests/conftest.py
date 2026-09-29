import os
import sys
import tempfile
from pathlib import Path

os.environ["FAKE_EMBED"] = "1"
os.environ["EDGE_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
