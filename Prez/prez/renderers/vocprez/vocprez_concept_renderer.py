from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from config import *
from renderers import Renderer
from profiles import vocpub, vocpub_supplied, skos
from models.vocprez import VocPrezConcept

templates = Jinja2Templates(TEMPLATES_DIRECTORY)


class VocPrezConceptRenderer(Renderer):
    profiles = {
        "vocpub": vocpub,
        "skos": skos,
        "vocpub_supplied": vocpub_supplied,
    }
    default_profile_token = "vocpub"

    def __init__(
        self,
        request: object,
        instance_uri: str,
    ) -> None:
        super().__init__(
            request,
            VocPrezConceptRenderer.profiles,
            VocPrezConceptRenderer.default_profile_token,
            instance_uri,
        )

    def set_concept(self, concept: VocPrezConcept) -> None:
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
            "vocprez/vocprez_concept.html",
            context=_template_context,
            headers=self.headers,
        )
    
    def _render_vocpub_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the vocpub profile for a concept"""
        _template_context = {
            "request": self.request,
            "concept": self.concept.to_dict(),
            "uri": self.instance_uri,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "vocprez/vocprez_concept_constructed.html",
            context=_template_context,
            headers=self.headers,
        )
    
    def _render_vocpub_rdf(self) -> Response:
        """Renders the RDF representation of the vocpub profile for a concept"""
        return Response(content="test vocpub RDF")

    def _render_vocpub(self, template_context: Union[Dict, None]):
        """Renders the vocpub profile for a concept"""
        if self.mediatype == "text/html":
            return self._render_vocpub_html(template_context)
        else:  # all other formats are RDF
            return self._render_vocpub_rdf()
    
    def _render_vocpub_supplied_rdf(self) -> Response:
        """Renders the RDF representation of the vocpub_supplied profile for a concept"""
        return Response(content="test vocpub_supplied RDF")

    def _render_vocpub_supplied(self, template_context: Union[Dict, None]):
        """Renders the vocpub_supplied profile for a concept"""
        if self.mediatype == "text/html":
            return self._render_dcat_html(template_context)
        else:  # all other formats are RDF
            return self._render_vocpub_supplied_rdf()

    def render(
        self, template_context: Optional[Dict] = None
    ) -> Union[
        PlainTextResponse, templates.TemplateResponse, Response, JSONResponse, None
    ]:
        if self.error is not None:
            return PlainTextResponse(self.error, status_code=400)
        elif self.profile == "alt":
            return self._render_alt(template_context)
        elif self.profile == "vocpub":
            return self._render_vocpub(template_context)
        elif self.profile == "vocpub_supplied":
            return self._render_vocpub_supplied(template_context)
        else:
            return None
