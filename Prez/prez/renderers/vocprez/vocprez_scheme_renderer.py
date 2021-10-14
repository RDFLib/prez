from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from config import *
from renderers import Renderer
from profiles import skos, dcat
from models.vocprez import VocPrezScheme

templates = Jinja2Templates(TEMPLATES_DIRECTORY)


class VocPrezSchemeRenderer(Renderer):
    profiles = {"dcat": dcat, "skos": skos}
    default_profile_token = "dcat"

    def __init__(
        self, request: object, instance_uri: str, scheme: VocPrezScheme
    ) -> None:
        super().__init__(
            request,
            VocPrezSchemeRenderer.profiles,
            VocPrezSchemeRenderer.default_profile_token,
            instance_uri,
        )
        self.scheme = scheme

    # def _render_skos_html(
    #     self, template_context: Union[Dict, None]
    # ) -> templates.TemplateResponse:
    #     """Renders the HTML representation of the skos profile for a scheme"""
    #     _template_context = {
    #         "request": self.request,
    #         "scheme": self.scheme.to_dict(),
    #         "uri": self.instance_uri,
    #     }
    #     if template_context is not None:
    #         _template_context.update(template_context)
    #     return templates.TemplateResponse(
    #         "vocprez_scheme.html", context=_template_context, headers=self.headers
    #     )

    def _render_skos_rdf(self) -> Response:
        """Renders the RDF representation of the skos profile for a scheme"""
        return Response(content="test skos RDF")

    def _render_skos(self, template_context: Union[Dict, None]):
        """Renders the skos profile for a scheme"""
        if self.mediatype == "text/html":
            return self._render_dcat_html(template_context)
        else:  # all other formats are RDF
            return self._render_skos_rdf()

    def _render_dcat_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the dcat profile for a scheme"""
        _template_context = {
            "request": self.request,
            "scheme": self.scheme.to_dict(),
            "uri": self.instance_uri,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "vocprez/vocprez_scheme.html", context=_template_context, headers=self.headers
        )

    def _render_dcat_rdf(self) -> Response:
        """Renders the RDF representation of the dcat profile for a scheme"""
        return Response(content="test dcat RDF")

    def _render_dcat(self, template_context: Union[Dict, None]):
        """Renders the dcat profile for a scheme"""
        if self.mediatype == "text/html":
            return self._render_dcat_html(template_context)
        else:  # all other formats are RDF
            return self._render_dcat_rdf()

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
        elif self.profile == "skos":
            return self._render_skos(template_context)
        else:
            return None
