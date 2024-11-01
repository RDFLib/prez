# from fastapi import Request
# from fastapi.responses import JSONResponse
#
#
# def create_validate_header_middleware(required_header: dict[str, str] | None):
#     async def validate_header(request: Request, call_next):
#         if required_header:
#             header_name, expected_value = next(iter(required_header.items()))
#             if (
#                 header_name not in request.headers
#                 or request.headers[header_name] != expected_value
#             ):
#                 return JSONResponse(  # attempted to use Exception and although it was caught it did not propagate
#                     status_code=400,
#                     content={
#                         "error": "Header Validation Error",
#                         "message": f"Missing or invalid header: {header_name}",
#                         "code": "HEADER_VALIDATION_ERROR",
#                     },
#                 )
#         return await call_next(request)
#
#     return validate_header


from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class ValidateHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, required_header: dict[str, str] | None):
        super().__init__(app)
        self.required_header = required_header

    async def dispatch(self, request: Request, call_next):
        if self.required_header:
            header_name, expected_value = next(iter(self.required_header.items()))
            if header_name not in request.headers or request.headers[header_name] != expected_value:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Header Validation Error",
                        "message": f"Missing or invalid header: {header_name}",
                        "code": "HEADER_VALIDATION_ERROR"
                    }
                )
        response = await call_next(request)
        return response
