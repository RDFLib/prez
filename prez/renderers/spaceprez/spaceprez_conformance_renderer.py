from typing import Dict, Optional, Union

from connegp import MEDIATYPE_NAMES
from fastapi.responses import Response, JSONResponse, PlainTextResponse

from prez.renderers import Renderer
from prez.utils import templates
from prez.config import *


class SpacePrezConformanceRenderer(Renderer):

    conformsTo = [
        {
            "title": "Conformance Class Core",
            "url": "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
        },
        {
            "title": "Conformance Class GeoJSON",
            "url": "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
        },
        {
            "title": "Conformance Class HTML",
            "url": "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html",
        },
        {
            "title": "Conformance Class OpenAPI 3.0",
            "url": "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas3",
        },
    ]

    def __init__(self, request: object) -> None:
        super().__init__(request, PREZ.Conformance, PREZ.Conformance, PREZ.Conformance)

    def _render_oai_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the OGC Features Core profile for the conformance page"""
        _template_context = {
            "request": self.request,
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "profiles": self.profile_details.available_profiles_dict,
            "default_profile": self.profile_details.default_profile,
            "conformsTo": SpacePrezConformanceRenderer.conformsTo,
            "mediatype_names": dict(
                MEDIATYPE_NAMES, **{"application/geo+json": "GeoJSON"}
            ),
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "spaceprez/spaceprez_conformance.html",
            context=_template_context,
            headers=self.headers,
        )

    def _render_oai_json(self) -> JSONResponse:
        """Renders the JSON representation of the OGC Features Core profile for the conformance page"""
        content = {
            "conformsTo": [
                conform["url"] for conform in SpacePrezConformanceRenderer.conformsTo
            ]
        }

        return JSONResponse(
            content=content,
            media_type="application/json",
            headers=self.headers,
        )

    def _render_oai(self, template_context: Union[Dict, None]):
        """Renders the OGC Features Core profile for the conformance page"""
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
