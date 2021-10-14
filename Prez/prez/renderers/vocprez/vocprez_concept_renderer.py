from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from config import *
from renderers import Renderer
from profiles import dcat, sdo
from models.vocprez import VocPrezConcept

templates = Jinja2Templates(TEMPLATES_DIRECTORY)


class VocPrezConceptRenderer(Renderer):
    profiles = {"dcat": dcat, "sdo": sdo}
    default_profile_token = "dcat"

    def __init__(
        self, request: object, instance_uri: str, concept: VocPrezConcept
    ) -> None:
        super().__init__(
            request,
            VocPrezConceptRenderer.profiles,
            VocPrezConceptRenderer.default_profile_token,
            instance_uri,
        )
        self.concept = concept

    def _render_dcat_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the DCAT profile for a concept"""
        _template_context = {
            "request": self.request,
            "concept": self.concept.to_dict(),
            "uri": self.instance_uri,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "vocprez/vocprez_concept.html", context=_template_context, headers=self.headers
        )

    def _render_dcat_rdf(self) -> Response:
        """Renders the RDF representation of the DCAT profile for a concept"""
        return Response(content="test DCAT RDF")

    def _render_dcat(self, template_context: Union[Dict, None]):
        """Renders the DCAT profile for a concept"""
        if self.mediatype == "text/html":
            return self._render_dcat_html(template_context)
        else:  # all other formats are RDF
            return self._render_dcat_rdf()

    def _render_sdo_rdf(self) -> Response:
        """Renders the RDF representation of the SDO profile for a concept"""
        return Response(content="test SDO RDF")

    def _render_sdo(self) -> Response:
        """Renders the SDO profile for a concept"""
        return self._render_sdo_rdf()

    def render(
        self, template_context: Optional[Union[Dict, None]] = None
    ) -> Union[
        PlainTextResponse, templates.TemplateResponse, Response, JSONResponse, None
    ]:
        if self.error is not None:
            return PlainTextResponse(self.error, status_code=400)
        elif self.profile == "alt":
            return self._render_alt(template_context)
        elif self.profile == "dcat":
            return self._render_dcat(template_context)
        elif self.profile == "sdo":
            return self._render_sdo()
        else:
            return None
