import csv
from io import StringIO

from connegp import MEDIATYPE_NAMES
from fastapi.responses import Response, JSONResponse, PlainTextResponse
from typing import Dict, Optional, Union

from prez.config import *
from prez.models.catprez import CatPrezCatalog
from prez.renderers import Renderer
from prez.services.catprez_service import get_catalog_uri
from prez.utils import templates


class CatPrezCatalogRenderer(Renderer):
    def __init__(
        self,
        request: object,
    ) -> None:
        self.catalog_id, self.catalog_uri = get_catalog_uri(
            request.path_params.get("catalog_id"),
            request.query_params.get("uri"),
        )
        super().__init__(
            request,
            self.catalog_uri,
            DCAT.Catalog,
            DCAT.Catalog,
        )

    def set_catalog(self, catalog: CatPrezCatalog) -> None:
        self.catalog = catalog

    def _generate_dcat_rdf(self) -> Graph:
        r = self.catalog.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX prov: <{PROV}>

            CONSTRUCT {{
                ?c
                    a dcat:Catalog ;
                    dcterms:title ?title ;
                    dcterms:description ?description ;
                    dcterms:created ?created ;
                    dcterms:modified ?modified ;
                    dcterms:creator ?creator ;
                    dcterms:publisher ?publisher ;
                    dcterms:hasPart ?resource .
            }}
            WHERE {{
                BIND (<{self.catalog.uri}> AS ?c)
                ?c
                    a dcat:Catalog ;
                    dcterms:title ?title ;
                    dcterms:description ?description ;
                    dcterms:created ?created ;
                    dcterms:modified ?modified ;
                    dcterms:creator ?creator ;
                    dcterms:publisher ?publisher ;
                    dcterms:hasPart ?resource .
            }}
        """
        )

        g = r.graph
        g.bind("dcat", DCAT)
        g.bind("dcterms", DCTERMS)
        return g

    def _render_dcat_rdf(self) -> Response:
        """Renders the RDF representation of the dcat profile for a catalog"""
        return Response(
            self._generate_dcat_rdf().serialize(format=self.mediatype),
            media_type=self.mediatype
        )

    def _render_dcat_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the dcat profile for a catalog"""
        # get the Resources' details
        parts = []
        for o in self.catalog.graph.objects(None, DCTERMS.hasPart):
            lbl = None
            id = None
            for p, o2 in self.catalog.graph.predicate_objects(o):
                if p == RDFS.label or p == DCTERMS.type:
                    lbl = str(o2)
                elif p == DCTERMS.identifier:
                    id = str(o2)
            if lbl is not None and id is not None:
                parts.append((id, lbl))

        _template_context = {
            "request": self.request,
            "catalog": self.catalog.to_dict(),
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "profiles": self.profile_details.available_profiles_dict,
            "default_profile": self.profile_details.default_profile,
            "mediatype_names": MEDIATYPE_NAMES,
            "parts": parts,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "catprez/catprez_catalog.html",
            context=_template_context,
            headers=self.headers,
        )

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
        elif self.profile == "dcat":
            if self.mediatype == "text/html":
                return self._render_dcat_html(template_context)
            else:  # all other formats are RDF
                return self._render_dcat_rdf()
        else:
            return None
