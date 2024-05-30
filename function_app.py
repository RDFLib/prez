import os
import azure.functions as func

try:
    from prez.app import assemble_app
except ImportError:
    assemble_app = None

if assemble_app is None:
    raise RuntimeError("Cannot import prez in the Azure function app. Check requirements.py and pyproject.toml.")

# This is the base URL path that Prez routes will stem from
# must _start_ in a slash, but _not end_ in slash, eg: /prez
env_root_path = os.getenv("FUNCTION_APP_ROOT_PATH", "/")
ROOT_PATH = env_root_path.strip()

prez_app = assemble_app(root_path=ROOT_PATH)

app = func.AsgiFunctionApp(app=prez_app, http_auth_level=func.AuthLevel.FUNCTION)
