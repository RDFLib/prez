from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from connegp import MEDIATYPE_NAMES

from config import *
from renderers import Renderer

from models.spaceprez import SpacePrezFeatureCollection
from utils import templates


class SpacePrezFeatureCollectionRenderer(Renderer):
    def __init__(
        self, request: object, profiles: dict, default_profile: str, instance_uri: str
    ) -> None:
        super().__init__(
            request,
            profiles,
            default_profile,
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
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "profiles": self.profiles,
            "default_profile": self.default_profile_token,
            "mediatype_names": dict(
                MEDIATYPE_NAMES, **{"application/geo+json": "GeoJSON"}
            ),
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "spaceprez/spaceprez_feature_collection.html",
            context=_template_context,
            headers=self.headers,
        )

    # def _render_oai_json(self) -> JSONResponse:
    #     """Renders the JSON representation of the OAI profile for a feature collection"""
    #     return JSONResponse(
    #         content={"test": "test"},
    #         media_type="application/json",
    #         headers=self.headers,
    #     )

    def _render_oai_geojson(self) -> JSONResponse:
        """Renders the GeoJSON representation of the OAI profile for a feature collection"""
        content = self.collection.to_geojson()

        content["links"] = [
            {
                "href": str(self.request.url),
                "rel": "self",
                "type": self.mediatype,
                "title": "this document",
            },
            {
                "href": str(self.request.base_url)[:-1] + str(self.request.url.path),
                "rel": "alternate",
                "type": "text/html",
                "title": "this document as HTML",
            },
        ]

        return JSONResponse(
            content=content,
            media_type="application/geo+json",
            headers=self.headers,
        )

    def _render_oai(self, template_context: Union[Dict, None]):
        """Renders the OAI profile for a feature collection"""
        if self.mediatype == "text/html":
            return self._render_oai_html(template_context)
        else:  # else return GeoJSON
            return self._render_oai_geojson()

    def _generate_geo_rdf(self) -> Graph:
        """Generates a Graph of the GeoSPARQL representation"""
        r = self.collection.graph.query(
            f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        PREFIX rdfs: <{RDFS}>
        CONSTRUCT {{
            ?fc a geo:FeatureCollection ;
                ?fc_pred ?fc_o ;
                geo:hasBoundingBox ?geom ;
                rdfs:member ?mem .
            ?geom ?geom_p ?geom_o .
            ?d a dcat:Dataset ;
                rdfs:member ?fc .
        }}
        WHERE {{
            BIND (<{self.collection.uri}> AS ?fc)
            ?fc a geo:FeatureCollection ;
                ?fc_pred ?fc_o ;
                rdfs:member ?mem .
            FILTER (STRSTARTS(STR(?fc_pred), STR(geo:)))
            OPTIONAL {{
                ?fc geo:hasBoundingBox ?geom .
                ?geom ?geom_p ?geom_o .
            }}
            ?d a dcat:Dataset ;
                rdfs:member ?fc .
        }}
        """
        )

        g = r.graph
        g.bind("dcat", DCAT)
        g.bind("dcterms", DCTERMS)
        g.bind("geo", GEO)
        g.bind("rdfs", RDFS)

        return g

    def _render_geo_rdf(self) -> Response:
        """Renders the RDF representation of the GeoSPAQRL profile for a feature collection"""
        g = self._generate_geo_rdf()
        return self._make_rdf_response(g)

    def _render_geo(self):
        """Renders the GeoSPARQL profile for a feature collection"""
        return self._render_geo_rdf()

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
        elif self.profile == "geo":
            return self._render_geo()
        else:
            return None
