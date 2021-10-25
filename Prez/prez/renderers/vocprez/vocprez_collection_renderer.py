from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from config import *
from renderers import Renderer
from profiles import skos, dcat
from models.vocprez import VocPrezCollection

templates = Jinja2Templates(TEMPLATES_DIRECTORY)


class VocPrezCollectionRenderer(Renderer):
    profiles = {"dcat": dcat, "skos": skos}
    default_profile_token = "dcat"

    def __init__(
        self,
        request: object,
        instance_uri: str,
    ) -> None:
        super().__init__(
            request,
            VocPrezCollectionRenderer.profiles,
            VocPrezCollectionRenderer.default_profile_token,
            instance_uri,
        )

    def set_collection(self, collection: VocPrezCollection) -> None:
        self.collection = collection

    # def _render_skos_html(
    #     self, template_context: Union[Dict, None]
    # ) -> templates.TemplateResponse:
    #     """Renders the HTML representation of the skos profile for a collection"""
    #     _template_context = {
    #         "request": self.request,
    #         "collection": self.collection.to_dict(),
    #         "uri": self.instance_uri,
    #     }
    #     if template_context is not None:
    #         _template_context.update(template_context)
    #     return templates.TemplateResponse(
    #         "vocprez_collection.html", context=_template_context, headers=self.headers
    #     )

    def _render_skos_rdf(self) -> Response:
        """Renders the RDF representation of the skos profile for a collection"""
        return Response(content="test skos RDF")

    def _render_skos(self, template_context: Union[Dict, None]):
        """Renders the skos profile for a collection"""
        if self.mediatype == "text/html":
            return self._render_dcat_html(template_context)
        else:  # all other formats are RDF
            return self._render_skos_rdf()

    def _render_dcat_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the dcat profile for a collection"""
        _template_context = {
            "request": self.request,
            "collection": self.collection.to_dict(),
            "uri": self.instance_uri,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "vocprez/vocprez_collection.html",
            context=_template_context,
            headers=self.headers,
        )

    def _render_dcat_rdf(self) -> Response:
        """Renders the RDF representation of the dcat profile for a collection"""
        return Response(content="test dcat RDF")

    def _render_dcat(self, template_context: Union[Dict, None]):
        """Renders the dcat profile for a collection"""
        if self.mediatype == "text/html":
            return self._render_dcat_html(template_context)
        else:  # all other formats are RDF
            return self._render_dcat_rdf()

    def render(
        self, template_context: Optional[Dict] = None
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
