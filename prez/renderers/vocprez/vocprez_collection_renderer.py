from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from rdflib import Graph
from rdflib.namespace import SKOS, PROV, DCTERMS
from connegp import MEDIATYPE_NAMES

from config import *
from renderers import Renderer
from profiles import skos, vocpub, vocpub_supplied, dd
from models.vocprez import VocPrezCollection
from utils import templates


class VocPrezCollectionRenderer(Renderer):
    profiles = {
        "vocpub": vocpub,
        "skos": skos,
        "dd": dd,
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
            VocPrezCollectionRenderer.profiles,
            VocPrezCollectionRenderer.default_profile_token,
            instance_uri,
        )

    def set_collection(self, collection: VocPrezCollection) -> None:
        self.collection = collection

    def _generate_skos_rdf(self) -> Graph:
        r = self.collection.graph.query(
            f"""
            PREFIX skos: <{SKOS}>
            CONSTRUCT {{
                ?coll ?coll_pred ?coll_o .
                ?c skos:prefLabel ?c_label .
            }}
            WHERE {{
                BIND (<{self.collection.uri}> AS ?coll)
                ?coll ?coll_pred ?coll_o ;
                    skos:member ?c .
                FILTER (STRSTARTS(STR(?coll_pred), STR(skos:)))
                ?c skos:prefLabel ?c_label .
            }}
        """
        )

        g = r.graph
        g.bind("skos", SKOS)

        return g

    def _render_skos_rdf(self) -> Response:
        """Renders the RDF representation of the skos profile for a collection"""
        g = self._generate_skos_rdf()
        return self._make_rdf_response(g)

    def _render_skos(self):
        """Renders the skos profile for a collection"""
        return self._render_skos_rdf()

    def _render_vocpub_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the vocpub profile for a collection"""
        _template_context = {
            "request": self.request,
            "collection": self.collection.to_dict(),
            "uri": self.instance_uri,
            "profiles": self.profiles,
            "default_profile": self.default_profile_token,
            "mediatype_names": MEDIATYPE_NAMES
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "vocprez/vocprez_collection.html",
            context=_template_context,
            headers=self.headers,
        )

    def _generate_vocpub_rdf(self) -> Graph:
        r = self.collection.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX prov: <{PROV}>
            PREFIX skos: <{SKOS}>
            CONSTRUCT {{
                ?coll a skos:Collection ;
                    skos:prefLabel ?label ;
                    skos:definition ?def ;
                    ?prov_pred ?prov ;
                    skos:member ?c .
                ?c a skos:Concept ;
                    skos:prefLabel ?c_label .
            }}
            WHERE {{
                BIND (<{self.collection.uri}> AS ?coll)
                ?coll a skos:Collection ;
                    skos:prefLabel ?label ;
                    skos:definition ?def ;
                    skos:member ?c .
                OPTIONAL {{
                    ?coll ?prov_pred ?prov .
                    FILTER (?prov_pred IN (dcterms:provenance, dcterms:source, prov:wasDerivedFrom))
                }}
                ?c a skos:Concept ;
                    skos:prefLabel ?c_label .
            }}
        """
        )

        g = r.graph
        g.bind("dcterms", DCTERMS)
        g.bind("prov", PROV)
        g.bind("skos", SKOS)

        return g

    def _render_vocpub_rdf(self) -> Response:
        """Renders the RDF representation of the vocpub profile for a collection"""
        g = self._generate_vocpub_rdf()
        return self._make_rdf_response(g)

    def _render_vocpub(self, template_context: Union[Dict, None]):
        """Renders the vocpub profile for a collection"""
        if self.mediatype == "text/html":
            return self._render_vocpub_html(template_context)
        else:  # all other formats are RDF
            return self._render_vocpub_rdf()

    def _render_vocpub_supplied(self):
        """Renders the vocpub_supplied profile for a collection"""
        return self._render_vocpub_rdf()
    
    def _render_dd_json(self) -> JSONResponse:
        """Renders the json representation of the dd profile for a collection"""
        return JSONResponse(
            content=self.collection.get_concept_flat_list(),
            media_type="application/json",
            headers=self.headers,
        )

    def _render_dd(self):
        """Renders the dd profile for a collection"""
        return self._render_dd_json()

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
            return self._render_vocpub_supplied()
        elif self.profile == "skos":
            return self._render_skos()
        elif self.profile == "dd":
            return self._render_dd()
        else:
            return None
