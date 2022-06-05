from typing import Dict, Optional, Union

from connegp import MEDIATYPE_NAMES, RDF_MEDIATYPES
from fastapi.responses import Response, JSONResponse, PlainTextResponse

from config import *
from models.spaceprez import SpacePrezFeature
from renderers import Renderer
from utils import templates


class SpacePrezFeatureRenderer(Renderer):
    def __init__(
        self,
        request: object,
        instance_uri: str,
        available_profiles: dict,
        default_profile: str,
    ) -> None:
        super().__init__(
            request,
            available_profiles,
            default_profile,
            instance_uri,
        )

    def set_feature(self, feature: SpacePrezFeature) -> None:
        self.feature = feature

    def _render_oai_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the OAI profile for a feature"""
        _template_context = {
            "request": self.request,
            "feature": self.feature.to_dict(),
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.base_url),
            "profiles": self.profiles,
            "default_profile": self.default_profile_token,
            "mediatype_names": dict(
                MEDIATYPE_NAMES, **{"application/geo+json": "GeoJSON"}
            ),
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "spaceprez/spaceprez_feature.html",
            context=_template_context,
            headers=self.headers,
        )

    def _render_oai_geojson(self) -> JSONResponse:
        """Renders the GeoJSON representation of the OAI profile for a feature"""

        content = self.feature.to_geojson()

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
            {
                "href": self.request.url_for(
                    "feature_collection",
                    dataset_id=self.feature.dataset["id"],
                    collection_id=self.feature.collection["id"],
                ),
                "rel": "collection",
                "type": "text/html",
                "title": "the collection document",
            },
        ]

        return JSONResponse(
            content=content,
            media_type="application/geo+json",
            headers=self.headers,
        )

    def _render_oai(self, template_context: Union[Dict, None]):
        """Renders the OAI profile for a feature"""
        if self.mediatype == "text/html":
            return self._render_oai_html(template_context)
        else:  # else return GeoJSON
            return self._render_oai_geojson()

    def _generate_geo_rdf(self) -> Graph:
        """Generates a Graph of the GeoSPARQL representation"""
        r = self.feature.graph.query(
            f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        CONSTRUCT {{
            ?f a geo:Feature ;
                ?f_pred ?f_o ;
                geo:hasGeometry ?geom ;
                geo:hasArea ?area .
            ?geom ?geom_p ?geom_o .
            ?area ?area_p ?area_o .
            ?fc a geo:FeatureCollection ;
                rdfs:member ?f .
        }}
        WHERE {{
            BIND (<{self.feature.uri}> AS ?f)
            ?f a geo:Feature ;
                ?f_pred ?f_o .
            FILTER (STRSTARTS(STR(?f_pred), STR(geo:)))
            OPTIONAL {{
                ?f geo:hasGeometry ?geom .
                ?geom ?geom_p ?geom_o .
            }}
            OPTIONAL {{
                ?f geo:hasArea ?area .
                ?area ?area_p ?area_o .
            }}
            ?fc a geo:FeatureCollection ;
                rdfs:member ?f .
        }}
        """
        )

        g = r.graph
        g.bind("dcterms", DCTERMS)
        g.bind("geo", GEO)

        return g

    def _render_geo_rdf(self) -> Response:
        """Renders the RDF representation of the GeoSPAQRL profile for a feature"""
        g = self._generate_geo_rdf()
        return self._make_rdf_response(g)

    def _render_geo(self):
        """Renders the GeoSPARQL profile for a feature"""
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
        elif self.mediatype == "text/html":
            return self._render_oai_html(template_context)
        elif self.mediatype == "application/geo+json":
            return self._render_oai_geojson()
        elif self.mediatype in RDF_MEDIATYPES:
            return self._make_rdf_response(self.feature.uri, self.feature.graph)
