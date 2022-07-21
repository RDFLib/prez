from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from connegp import MEDIATYPE_NAMES, RDF_MEDIATYPES

from prez.config import *
from prez.renderers import Renderer

from prez.models.spaceprez import SpacePrezDataset
from prez.utils import templates
from prez.services.spaceprez_service import get_object_uri_and_classes


class SpacePrezDatasetRenderer(Renderer):
    def __init__(self, request: object) -> None:
        (
            _,  # feature_id
            _,  # collection_id
            self.dataset_id,
            _,  # feature_uri
            _,  # collection
            self.instance_uri,
            _,  # classes
        ) = get_object_uri_and_classes(
            None,  # feature_id
            None,  # collection_id
            request.path_params.get("dataset_id"),
            None,  # feature_uri
            None,  # collection_uri
            request.query_params.get("uri"),
        )
        super().__init__(request, self.instance_uri, DCAT.Dataset, DCAT.Dataset)

    def set_dataset(self, dataset: SpacePrezDataset) -> None:
        self.dataset = dataset

    def _render_oai_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the OGC Features Core profile for a dataset"""
        _template_context = {
            "request": self.request,
            "dataset": self.dataset.to_dict(),
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
            "spaceprez/spaceprez_dataset.html",
            context=_template_context,
            headers=self.headers,
        )

    def _render_oai_json(self) -> JSONResponse:
        """Renders the JSON representation of the OGC Features Core profile for a dataset"""
        content = {
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
            ]
        }

        return JSONResponse(
            content=content,
            media_type="application/json",
            headers=self.headers,
        )

    def _render_oai(self, template_context: Union[Dict, None]):
        """Renders the OGC Features Core profile for a dataset"""
        if self.mediatype == "text/html":
            return self._render_oai_html(template_context)
        else:  # else return JSON
            return self._render_oai_json()

    def _render_dcat_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the DCAT profile for a dataset"""
        return self._render_oai_html(template_context)

    def _generate_dcat_rdf(self) -> Graph:
        """Generates a Graph of the DCAT representation"""
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

        sparql = URIRef(self.instance_uri + "/sparql")
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
        return self._make_rdf_response(g)

    def _render_dcat(self, template_context: Union[Dict, None]):
        """Renders the DCAT profile for a dataset"""
        if self.mediatype == "text/html":
            return self._render_dcat_html(template_context)
        else:  # all other formats are RDF
            return self._render_dcat_rdf()

    def _generate_geo_rdf(self) -> Graph:
        """Generates a Graph of the GeoSPARQL representation"""
        r = self.dataset.graph.query(
            f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        CONSTRUCT {{
            ?d a dcat:Dataset ;
                ?d_pred ?d_o ;
                geo:hasBoundingBox ?geom .
            ?geom ?geom_p ?geom_o .
        }}
        WHERE {{
            BIND (<{self.dataset.uri}> AS ?d)
            ?d a dcat:Dataset .
            OPTIONAL {{
                ?d ?d_pred ?d_o .
                FILTER (STRSTARTS(STR(?d_pred), STR(geo:)))
            }}
            OPTIONAL {{
                ?d geo:hasBoundingBox ?geom .
                ?geom ?geom_p ?geom_o .
            }}
        }}
        """
        )

        g = r.graph
        g.bind("dcat", DCAT)
        g.bind("dcterms", DCTERMS)
        g.bind("geo", GEO)

        return g

    def _render_geo_rdf(self) -> Response:
        """Renders the RDF representation of the GeoSPAQRL profile for a dataset"""
        g = self._generate_geo_rdf()
        return self._make_rdf_response(g)

    def _render_geo(self):
        """Renders the GeoSPARQL profile for a dataset"""
        return self._render_geo_rdf()

    def _render_oai_geojson(self) -> JSONResponse:
        """Renders the GeoJSON representation of the OGC Features Core profile for a Dataset"""

        """
        {
            "request": self.request,
            "dataset": self.dataset.to_dict(),
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "profiles": self.profile_details.available_profiles_dict,
            "default_profile": self.profile_details.default_profile,
            "mediatype_names": dict(
                MEDIATYPE_NAMES, **{"application/geo+json": "GeoJSON"}
            ),
        }
        
        {
            "uri": self.uri,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "properties": self._get_properties(),
            "geometries": self.geometries,
            "collections": self.collections,
        }
        """
        content = self.dataset.to_geojson()

        """
        { 
            "href": "http://data.example.org/",
            "rel": "self", 
            "type": "application/json", 
            "title": "this document" },
        { 
            "href": "http://data.example.org/api",
            "rel": "service-desc", 
            "type": "application/vnd.oai.openapi+json;version=3.0", 
            "title": "the API definition" },
        { 
            "href": "http://data.example.org/api.html",
            "rel": "service-doc", 
            "type": "text/html", 
            "title": "the API documentation" },
        { 
            "href": "http://data.example.org/conformance",
            "rel": "conformance", 
            "type": "application/json", 
            "title": "OGC API conformance classes implemented by this server" },
        { 
            "href": "http://data.example.org/collections",
            "rel": "data", 
            "type": "application/json", 
            "title": "Information about the feature collections" }        
        """
        content["links"] = [
            {
                "href": str(self.request.url),
                "rel": "self",
                "type": self.mediatype,
                "title": "This document",
            },
            {
                "href": self.request.url_for("index") + "api",
                "rel": "service-desc",
                "type": "application/vnd.oai.openapi+json;version=3.0",
                "title": "The API definition",
            },
            {
                "href": self.request.url_for("index") + "api.html",
                "rel": "service-doc",
                "type": "text/html",
                "title": "The API documentation",
            },
            {
                "href": self.request.url_for("conformance"),
                "rel": "conformance",
                "type": "application/json",
                "title": "OGC API conformance classes implemented by this server",
            },
            {
                "href": str(self.request.url).split("?_profile=oai")[0]
                + "?_profile=oai"
                + "&"
                + "_mediatype=text/html",
                "rel": "alternate",
                "type": "text/html",
                "title": "this document as HTML",
            },
            {
                "href": self.request.url_for(
                    "feature_collections_endpoint", dataset_id=self.dataset_id
                ),
                "rel": "data",
                "type": "text/html",
                "title": "Information about the feature collections",
            },
            {
                "href": self.request.url_for(
                    "feature_collections_endpoint", dataset_id=self.dataset_id
                )
                + "?_mediatype=application/geo+json",
                "rel": "data",
                "type": "application/geo+json",
                "title": "Information about the feature collections in GeoJSON",
            },
        ]

        return JSONResponse(
            content=content,
            media_type="application/geo+json",
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
            return self._render_alt(
                template_context, alt_profiles_graph=alt_profiles_graph
            )
        elif self.mediatype == "text/html":
            return self._render_oai_html(template_context)
        elif self.mediatype == "application/geo+json":
            return self._render_oai_geojson()
        elif self.mediatype in RDF_MEDIATYPES:
            return self._make_rdf_response(self.dataset.uri, self.dataset.graph)
        else:
            return None
