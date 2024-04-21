import azure.functions as func

try:
    from prez.app import app as prez_app
except ImportError:
    prez_app = None

app = func.AsgiFunctionApp(app=prez_app, http_auth_level=func.AuthLevel.FUNCTION)
