from typing import Dict, Optional, Union

from connegp import MEDIATYPE_NAMES, RDF_MEDIATYPES
from fastapi.responses import Response, JSONResponse, PlainTextResponse

from prez.config import *
from prez.models.spaceprez import SpacePrezFeature
from prez.renderers import Renderer
from prez.services.spaceprez_service import get_object_uri_and_classes
from prez.utils import templates
from starlette.requests import Request


class SpacePrezFeatureRenderer(Renderer):
    def __init__(
        self,
        request: Request,
    ) -> None:
        (
            self.feature_id,
            self.collection_id,
            self.dataset_id,
            self.instance_uri,
            _,  # collection_uri
            _,  # dataset_uri
            self.feature_classes,
        ) = get_object_uri_and_classes(
            request.path_params.get("feature_id"),
            request.path_params.get("collection_id"),
            request.path_params.get("dataset_id"),
            request.query_params.get("uri"),
            None,  # collection_uri
            None,  # dataset_uri
        )

        super().__init__(request, self.instance_uri, self.feature_classes, GEO.Feature)

    def set_feature(self, feature: SpacePrezFeature) -> None:
        self.feature = feature

    def _render_oai_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the OGC Features Core profile for a feature"""
        _template_context = {
            "request": self.request,
            "feature": self.feature.to_dict(),
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
            "spaceprez/spaceprez_feature.html",
            context=_template_context,
            headers=self.headers,
        )

    def _render_oai_geojson(self) -> JSONResponse:
        """Renders the GeoJSON representation of the OGC Features Core profile for a Feature"""

        content = self.feature.to_geojson()

        content["links"] = [
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
            {
                "href": self.request.url_for(
                    "feature_collection_endpoint",
                    dataset_id=self.dataset_id,
                    collection_id=self.collection_id,
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
        """Renders the OGC Features Core profile for a feature"""
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
        elif self.profile == "oai" and self.mediatypes_requested[0] in RDF_MEDIATYPES:
            # ignore secondary mediatypes requested - assume connegp has done its job
            # change the mediatype to that requested, and return an RDF response
            self.mediatype = self.mediatypes_requested[0]
            return self._make_rdf_response(self.feature.uri, self.feature.graph)
        elif self.mediatype == "text/html":
            return self._render_oai_html(template_context)
        elif self.mediatype == "application/geo+json":
            return self._render_oai_geojson()
        elif self.mediatype in RDF_MEDIATYPES:
            return self._make_rdf_response(self.feature.uri, self.feature.graph)
