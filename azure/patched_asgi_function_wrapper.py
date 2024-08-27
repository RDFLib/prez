from typing import Union, TYPE_CHECKING
from copy import copy
import azure.functions as func
from azure.functions.decorators.http import HttpMethod
from azure.functions._http_asgi import AsgiMiddleware, AsgiRequest, AsgiResponse
from azure.functions._http_wsgi import WsgiMiddleware
from azure.functions._abc import Context
from azure.functions import HttpRequest

# -------------------
# Create a patched AsgiFunctionApp to fix the ASGI scope state issue
# -------------------
# See https://github.com/Azure/azure-functions-python-worker/issues/1566
class MyAsgiMiddleware(AsgiMiddleware):
    async def _handle_async(self, req, context):
        asgi_request = AsgiRequest(req, context)
        scope = asgi_request.to_asgi_http_scope()
        # shallow copy the state as-per the ASGI spec
        scope["state"] = copy(self.state)  # <-- this is the patch, add the state to the scope
        asgi_response = await AsgiResponse.from_app(self._app,
                                                    scope,
                                                    req.get_body())
        return asgi_response.to_func_response()

# -------------------
# Create a patched AsgiFunctionApp to fix the double-slash route issue
# -------------------
# See https://github.com/Azure/azure-functions-python-worker/issues/1310
class AsgiFunctionApp(func.AsgiFunctionApp):
    def __init__(self, app, http_auth_level):
        super(AsgiFunctionApp, self).__init__(None, http_auth_level=http_auth_level)
        self._function_builders.clear()
        self.middleware = MyAsgiMiddleware(app)
        self._add_http_app(self.middleware)
        self.startup_task_done = False

    def _add_http_app(
            self, http_middleware: Union[AsgiMiddleware, WsgiMiddleware]
    ) -> None:
        """Add an Asgi app integrated http function.

        :param http_middleware: :class:`WsgiMiddleware`
                                or class:`AsgiMiddleware` instance.

        :return: None
        """

        asgi_middleware: AsgiMiddleware = http_middleware

        @self.http_type(http_type="asgi")
        @self.route(
            methods=(method for method in HttpMethod),
            auth_level=self.auth_level,
            route="{*route}",  # <-- this is the patch, removed the leading slash from the route
        )
        async def http_app_func(req: HttpRequest, context: Context):
            if not self.startup_task_done:
                success = await asgi_middleware.notify_startup()
                if not success:
                    raise RuntimeError("ASGI middleware startup failed.")
                self.startup_task_done = True

            return await asgi_middleware.handle_async(req, context)
