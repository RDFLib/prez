from typing import Dict, Optional, Union

from connegp import MEDIATYPE_NAMES
from fastapi.responses import Response, JSONResponse, PlainTextResponse

from prez.config import *
from prez.renderers import Renderer
from prez.utils import templates
from starlette.requests import Request


class SpacePrezHomeRenderer(Renderer):
    def __init__(self, request: Request) -> None:
        super().__init__(request, PREZ.Home, PREZ.Home, PREZ.Home)

    def _render_oai_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the OGC Features Core profile for the home page"""
        _template_context = {
            "request": self.request,
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "profiles": self.profile_details.available_profiles_dict,
            "default_profile": self.profile_details.default_profile,
            "mediatype_names": dict(
                MEDIATYPE_NAMES, **{"application/geo+json": "GeoJSON"}
            ),
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "spaceprez/spaceprez_home.html",
            context=_template_context,
            headers=self.headers,
        )

    def _render_oai_json(self) -> JSONResponse:
        """Renders the JSON representation of the OGC Features Core profile for the home page"""
        content = {
            "title": SPACEPREZ_TITLE,
            "description": SPACEPREZ_DESC,
            "links": [
                {
                    "href": str(self.request.url),
                    "rel": "self",
                    "type": self.mediatype,
                    "title": "this document",
                },
                {
                    "href": str(self.request.url)[:-1] + str(self.request.url.path),
                    "rel": "alternate",
                    "type": "text/html",
                    "title": "this document as HTML",
                },
                {
                    "href": str(self.request.url) + "docs",
                    "rel": "service-doc",
                    "type": self.mediatype,
                    "title": "API Definition",
                },
                {
                    "href": self.request.url_for("conformance"),
                    "rel": "conformance",
                    "type": self.mediatype,
                    "title": "Conformance",
                },
                {
                    "href": self.request.url_for("datasets_endpoint"),
                    "rel": "data",
                    "type": self.mediatype,
                    "title": "Datasets",
                },
            ],
        }

        return JSONResponse(
            content=content,
            media_type="application/json",
            headers=self.headers,
        )

    def _render_oai(self, template_context: Union[Dict, None]):
        """Renders the OGC Features Core profile for the home page"""
        if self.mediatype == "text/html":
            return self._render_oai_html(template_context)
        else:  # else return JSON
            return self._render_oai_json()

    def render(
        self,
        template_context: Optional[Dict] = None,
        alt_profiles_graph: Optional[Graph] = None,
    ) -> Union[
        PlainTextResponse, templates.TemplateResponse, Response, JSONResponse, None
    ]:
        if self.error is not None:
            return PlainTextResponse(self.error, status_code=400)
        elif self.profile == "alt":
            return self._render_alt(template_context, alt_profiles_graph)
        elif self.profile == "oai":
            return self._render_oai(template_context)
        else:
            return None
