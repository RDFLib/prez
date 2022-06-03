from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from connegp import MEDIATYPE_NAMES

from config import *
from renderers import Renderer
from profiles.vocprez_profiles import skos, vocpub, vocpub_supplied, dd
from models.vocprez import VocPrezScheme
from utils import templates


class VocPrezSchemeRenderer(Renderer):
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
            VocPrezSchemeRenderer.profiles,
            VocPrezSchemeRenderer.default_profile_token,
            instance_uri,
        )

    def set_scheme(self, scheme: VocPrezScheme) -> None:
        self.scheme = scheme

    def _generate_skos_rdf(self) -> Graph:
        r = self.scheme.graph.query(
            f"""
            PREFIX skos: <{SKOS}>
            CONSTRUCT {{
                ?cs ?cs_pred ?cs_o .
                ?c ?c_pred ?c_o .
            }}
            WHERE {{
                BIND (<{self.scheme.uri}> AS ?cs)
                ?cs ?cs_pred ?cs_o .
                FILTER (STRSTARTS(STR(?cs_pred), STR(skos:)))
                ?c skos:inScheme ?cs ;
                    ?c_pred ?c_o .
                FILTER (STRSTARTS(STR(?c_pred), STR(skos:)))
            }}
        """
        )

        g = r.graph
        g.bind("skos", SKOS)

        return g

    def _render_skos_rdf(self) -> Response:
        """Renders the RDF representation of the skos profile for a scheme"""
        g = self._generate_skos_rdf()
        return self._make_rdf_response(g)

    def _render_skos(self):
        """Renders the skos profile for a scheme"""
        return self._render_skos_rdf()

    def _render_dd_json(self) -> JSONResponse:
        """Renders the json representation of the dd profile for a scheme"""
        return JSONResponse(
            content=self.scheme.get_concept_flat_list(),
            media_type="application/json",
            headers=self.headers,
        )

    def _render_dd(self):
        """Renders the dd profile for a scheme"""
        return self._render_dd_json()

    def _generate_vocpub_rdf(self) -> Graph:
        r = self.scheme.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX prov: <{PROV}>
            PREFIX skos: <{SKOS}>
            CONSTRUCT {{
                ?cs skos:prefLabel ?label ;
                    a skos:ConceptScheme ;
                    skos:definition ?def ;
                    dcterms:created ?created ;
                    dcterms:modified ?modified ;
                    dcterms:creator ?creator ;
                    dcterms:publisher ?publisher ;
                    ?prov_pred ?prov ;
                    skos:hasTopConcept ?tc .
                ?c skos:inScheme ?cs ;
                    a skos:Concept ;
                    skos:prefLabel ?c_label ;
                    skos:broader ?broader ;
                    skos:narrower ?narrower .
            }}
            WHERE {{
                BIND (<{self.scheme.uri}> AS ?cs)
                ?cs skos:prefLabel ?label ;
                    a skos:ConceptScheme ;
                    skos:definition ?def ;
                    dcterms:created ?created ;
                    dcterms:modified ?modified ;
                    dcterms:creator ?creator ;
                    dcterms:publisher ?publisher ;
                    ?prov_pred ?prov ;
                    skos:hasTopConcept ?tc .
                FILTER (?prov_pred IN (dcterms:provenance, dcterms:source, prov:wasDerivedFrom))
                ?c skos:inScheme ?cs ;
                    a skos:Concept ;
                    skos:prefLabel ?c_label .
                OPTIONAL {{
                    ?c skos:broader ?broader .
                }}
                OPTIONAL {{
                    ?c skos:narrower ?narrower .
                }}
            }}
        """
        )

        g = r.graph
        g.bind("dcterms", DCTERMS)
        g.bind("prov", PROV)
        g.bind("skos", SKOS)

        return g

    def _render_vocpub_rdf(self) -> Response:
        """Renders the RDF representation of the vocpub profile for a scheme"""
        g = self._generate_vocpub_rdf()
        return self._make_rdf_response(g)

    def _render_vocpub(self, template_context: Union[Dict, None]):
        """Renders the vocpub profile for a scheme"""
        if self.mediatype == "text/html":
            return self._render_vocpub_html(template_context)
        else:  # all other formats are RDF
            return self._render_vocpub_rdf()

    def _render_vocpub_supplied_rdf(self) -> Response:
        """Renders the RDF representation of the vocpub_supplied profile for a scheme"""
        return self._render_vocpub_rdf()

    def _render_vocpub_supplied(self, template_context: Union[Dict, None]):
        """Renders the vocpub_supplied profile for a scheme"""
        if self.mediatype == "text/html":
            return self._render_vocpub_html(template_context)
        else:  # all other formats are RDF
            return self._render_vocpub_supplied_rdf()

    def _render_vocpub_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the dcat profile for a scheme"""
        _template_context = {
            "request": self.request,
            "scheme": self.scheme.to_dict(),
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "profiles": self.profiles,
            "default_profile": self.default_profile_token,
            "mediatype_names": MEDIATYPE_NAMES,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "vocprez/vocprez_scheme.html",
            context=_template_context,
            headers=self.headers,
        )

    def render(
        self, template_context: Optional[Dict] = None,
        alt_profiles_graph: Optional[Graph] = None,
    ) -> Union[
        PlainTextResponse, templates.TemplateResponse, Response, JSONResponse, None
    ]:
        if self.error is not None:
            return PlainTextResponse(self.error, status_code=400)
        elif self.profile == "alt":
            return self._render_alt(template_context, alt_profiles_graph)
        elif self.profile == "skos":
            return self._render_skos()
        elif self.profile == "vocpub":
            return self._render_vocpub(template_context)
        elif self.profile == "vocpub_supplied":
            return self._render_vocpub_supplied(template_context)
        elif self.profile == "dd":
            return self._render_dd()
        else:
            return None
