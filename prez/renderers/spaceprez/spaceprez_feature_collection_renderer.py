from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import DCAT, DCTERMS, RDF
from connegp import MEDIATYPE_NAMES

from config import *
from renderers import Renderer
from profiles.spaceprez_profiles import oai, geo
from models.spaceprez import SpacePrezFeatureCollection
from utils import templates


class SpacePrezFeatureCollectionRenderer(Renderer):
    profiles = {"oai": oai, "geo": geo}
    default_profile_token = "oai"

    def __init__(self, request: object, instance_uri: str) -> None:
        super().__init__(
            request,
            SpacePrezFeatureCollectionRenderer.profiles,
            SpacePrezFeatureCollectionRenderer.default_profile_token,
            instance_uri,
        )

    def set_collection(self, collection: SpacePrezFeatureCollection) -> None:
        self.collection = collection

    def _render_oai_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the DCAT profile for a feature collection"""
        _template_context = {
            "request": self.request,
            "collection": self.collection.to_dict(),
            "uri": self.instance_uri,
            "profiles": self.profiles,
            "default_profile": self.default_profile_token,
            "mediatype_names": dict(MEDIATYPE_NAMES, **{"application/geo+json": "GeoJSON"}),
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "spaceprez/spaceprez_feature_collection.html",
            context=_template_context,
            headers=self.headers,
        )
    
    def _render_oai_json(self) -> JSONResponse:
        """Renders the JSON representation of the OAI profile for a feature collection"""
        return JSONResponse(
            content={"test": "test"},
            media_type="application/json",
            headers=self.headers,
        )
    
    def _render_oai_geojson(self) -> JSONResponse:
        """Renders the GeoJSON representation of the OAI profile for a feature collection"""
        return JSONResponse(
            content={"test": "test"},
            media_type="application/geo+json",
            headers=self.headers,
        )

    def _render_oai(self, template_context: Union[Dict, None]):
        """Renders the OAI profile for a feature collection"""
        if self.mediatype == "application/json":
            return self._render_oai_json()
        elif self.mediatype == "application/geo+json":
            return self._render_oai_geojson()
        else:  # else return HTML
            return self._render_oai_html(template_context)

    def _generate_geo_rdf(self) -> Graph:
        """Generates a Graph of the GeoSPARQL representation"""
        g = Graph()
        g.bind("dcat", DCAT)
        g.bind("dcterms", DCTERMS)
        ds = URIRef(self.dataset.uri)
        g.add((ds, RDF.type, DCAT.Dataset))
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

    def _render_geo_rdf(self) -> Response:
        """Renders the RDF representation of the GeoSPAQRL profile for a feature collection"""
        g = self._generate_geo_rdf()
        return self._make_rdf_response(g)

    def _render_geo(self):
        """Renders the GeoSPARQL profile for a feature collection"""
        return self._render_geo_rdf()
    
    def render(
        self, template_context: Optional[Dict] = None
    ) -> Union[
        PlainTextResponse, templates.TemplateResponse, Response, JSONResponse, None
    ]:
        if self.error is not None:
            return PlainTextResponse(self.error, status_code=400)
        elif self.profile == "alt":
            return self._render_alt(template_context)
        elif self.profile == "oai":
            return self._render_oai(template_context)
        elif self.profile == "geo":
            return self._render_geo()
        else:
            return None
