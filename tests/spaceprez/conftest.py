import os
from pathlib import Path
import sys

os.environ["SPACEPREZ_SPARQL_ENDPOINT"] = "http://localhost:3032/spaceprez"
PREZ_DIR = Path(__file__).parent.parent.parent.parent.absolute() / "prez"
os.environ["PREZ_DIR"] = str(PREZ_DIR)
os.environ["LOCAL_SPARQL_STORE"] = str(
    Path(Path(__file__).parent.parent / "local_sparql_store/store.py")
)

sys.path.insert(0, str(PREZ_DIR.absolute()))
