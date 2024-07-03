import os
import azure.functions as func


try:
    from prez.app import assemble_app
except ImportError:
    assemble_app = None


if assemble_app is None:
    raise RuntimeError(
        "Cannot import prez in the Azure function app. Check requirements.py and pyproject.toml."
    )


# This is the base URL path that Prez routes will stem from
# must _start_ in a slash, but _not end_ in slash, eg: /prez
env_root_path: str = os.getenv("FUNCTION_APP_ROOT_PATH", "")
ROOT_PATH: str = env_root_path.strip()
# Note, must be _empty_ string for no path prefix (not "/")
if ROOT_PATH == "/":
    ROOT_PATH = ""
env_auth_level: str = os.getenv("FUNCTION_APP_AUTH_LEVEL", "FUNCTION")
env_auth_level = env_auth_level.strip().upper()
if env_auth_level == "ADMIN":
    auth_level: func.AuthLevel = func.AuthLevel.ADMIN
elif env_auth_level == "ANONYMOUS":
    auth_level = func.AuthLevel.ANONYMOUS
else:
    auth_level = func.AuthLevel.FUNCTION

prez_app = assemble_app(root_path=ROOT_PATH)

app = func.AsgiFunctionApp(app=prez_app, http_auth_level=auth_level)

if __name__ == "__main__":
    from azure.functions import HttpRequest, Context
    import asyncio

    req = HttpRequest("GET", "/v", headers={}, body=b"")
    context = dict()
    loop = asyncio.get_event_loop()

    task = app.middleware.handle_async(req, context)
    resp = loop.run_until_complete(task)
    print(resp)
