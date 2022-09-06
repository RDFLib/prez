from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from connegp import MEDIATYPE_NAMES

from prez.config import *
from prez.renderers import Renderer
from prez.models.catprez import CatPrezResource
from prez.services.catprez_service import get_resource_uri
from prez.utils import templates


class CatPrezResourceRenderer(Renderer):
    def __init__(
        self,
        request: object,
    ) -> None:
        self.resource_id, self.resource_uri = get_resource_uri(
            request.path_params.get("resource_id"),
            request.query_params.get("uri"),
        )
        super().__init__(
            request,
            PREZ.CatPrezHome,
            PREZ.CatPrezHome,
            PREZ.CatPrezHome,
        )

    def set_resource(self, resource: CatPrezResource) -> None:
        self.resource = resource

    def _render_dcat_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the DCAT profile for a dataset"""
        parts = []
        for o in self.resource.graph.objects(None, DCTERMS.hasPart):
            lbl = None
            id = None
            for p, o2 in self.resource.graph.predicate_objects(o):
                if p == RDFS.label or p == DCTERMS.type:
                    lbl = str(o2)
                elif p == DCTERMS.identifier:
                    id = str(o2)
            if lbl is not None and id is not None:
                parts.append((id, lbl))

        _template_context = {
            "request": self.request,
            "resource": self.resource.to_dict(),
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "profiles": self.profile_details.available_profiles_dict,
            "default_profile": self.profile_details.default_profile,
            "mediatype_names": MEDIATYPE_NAMES,
            "catalog": {"title": "CatPrez System Catalogue", "id": "catprez"},
            "parts": parts,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "catprez/catprez_resource.html",
            context=_template_context,
            headers=self.headers,
        )

    def _generate_dcat_rdf(self) -> Graph:
        """Generates a Graph of the DCAT representation"""
        g = Graph()
        g.bind("dcat", DCAT)
        g.bind("dcterms", DCTERMS)
        ds = URIRef(self.dataset.uri)
        g.add((ds, RDF.type, DCAT.Resource))
        g.add((ds, DCTERMS.title, Literal(self.dataset.title)))
        g.add((ds, DCTERMS.description, Literal(self.dataset.description)))

        api = URIRef(self.instance_uri)
        g.add((api, DCAT.servesDataset, ds))
        g.add((api, RDF.type, DCAT.DataService))
        g.add((api, DCTERMS.title, Literal("System ConnegP API")))
        g.add(
            (
                api,
                DCTERMS.description,
                Literal(
                    "A Content Negotiation by Profile-compliant service that provides "
                    "access to all of this catalogue's information"
                ),
            )
        )
        g.add((api, DCTERMS.type, URIRef("http://purl.org/dc/dcmitype/Service")))
        g.add((api, DCAT.endpointURL, api))

        sparql = URIRef(self.instance_uri + "sparql")
        g.add((sparql, DCAT.servesDataset, ds))
        g.add((sparql, RDF.type, DCAT.DataService))
        g.add((sparql, DCTERMS.title, Literal("System SPARQL Service")))
        g.add(
            (
                sparql,
                DCTERMS.description,
                Literal(
                    "A SPARQL Protocol-compliant service that provides access to all "
                    "of this catalogue's information"
                ),
            )
        )
        g.add((sparql, DCTERMS.type, URIRef("http://purl.org/dc/dcmitype/Service")))
        g.add((sparql, DCAT.endpointURL, sparql))

        return g

    def _render_dcat_rdf(self) -> Response:
        """Renders the RDF representation of the DCAT profile for a dataset"""
        g = self._generate_dcat_rdf()
        return self._make_rdf_response(self.instance_uri, g)

    def _render_dcat(self, template_context: Union[Dict, None]):
        """Renders the DCAT profile for a dataset"""
        if self.mediatype == "text/html":
            return self._render_dcat_html(template_context)
        else:  # all other formats are RDF
            return self._render_dcat_rdf()

    def _generate_sdo_rdf(self) -> Graph:
        """Generates a Graph of the SDO representation"""
        g = Graph()
        g.bind("sdo", SDO)
        vs = URIRef(self.dataset.uri)
        g.add((vs, RDF.type, SDO.Dataset))
        g.add((vs, SDO.name, Literal(self.dataset.title)))
        g.add((vs, SDO.description, Literal(self.dataset.description)))

        return g

    def _render_sdo_rdf(self) -> Response:
        """Renders the RDF representation of the SDO profile for a dataset"""
        g = self._generate_sdo_rdf()
        return self._make_rdf_response(g)

    def _render_sdo(self) -> Response:
        """Renders the SDO profile for a dataset"""
        return self._render_sdo_rdf()

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
            return self._render_dcat(template_context)
        elif self.profile == "sdo":
            return self._render_sdo()
        else:
            return None
