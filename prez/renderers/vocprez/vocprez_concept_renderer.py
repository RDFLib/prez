from typing import Dict, Optional, Union

from connegp import MEDIATYPE_NAMES
from fastapi.responses import Response, JSONResponse, PlainTextResponse

from prez.config import *
from prez.models.vocprez import VocPrezConcept
from prez.renderers import Renderer
from prez.utils import templates
from prez.services.vocprez_service import get_concept_and_scheme_uri


class VocPrezConceptRenderer(Renderer):
    # profiles = {
    #     "vocpub": vocpub,
    #     "skos": skos,
    #     "vocpub_supplied": vocpub_supplied,
    #     "alt": alt,
    # }
    # default_profile_token = "vocpub"

    def __init__(
        self,
        request: object,
    ) -> None:
        (
            self.scheme_id,
            self.concept_id,
            self.concept_uri,
        ) = get_concept_and_scheme_uri(
            request.path_params.get("scheme_id"),
            request.path_params.get("concept_id"),
            request.query_params.get("uri"),
        )
        super().__init__(
            request,
            self.concept_uri,
            SKOS.Concept,
            SKOS.Concept,
        )

    def set_concept(self, concept: VocPrezConcept) -> None:
        self.concept = concept

    def _render_vocpub_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the vocpub profile for a concept"""
        _template_context = {
            "request": self.request,
            "concept": self.concept.to_dict(),
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "profiles": self.profile_details.available_profiles_dict,
            "default_profile": self.profile_details.default_profile,
            "mediatype_names": MEDIATYPE_NAMES,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "vocprez/vocprez_concept.html",
            context=_template_context,
            headers=self.headers,
        )

    def _generate_vocpub_rdf(self) -> Graph:
        r = self.concept.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX prov: <{PROV}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            CONSTRUCT {{
                ?c a skos:Concept ;
                    skos:prefLabel ?label ;
                    skos:definition ?def ;
                    ?prov_pred ?prov ;
                    skos:inScheme ?cs ;
                    skos:broader ?broader ;
                    skos:narrower ?narrower ;
                    rdfs:isDefinedBy ?defined .
                ?cs a skos:ConceptScheme ;
                    skos:prefLabel ?cs_label .
                ?defined a skos:ConceptScheme ;
                    skos:prefLabel ?defined_label .
                ?broader a skos:Concept ;
                    skos:prefLabel ?broader_label .
                ?narrower a skos:Concept ;
                    skos:prefLabel ?narrower_label .
            }}
            WHERE {{
                BIND (<{self.concept.uri}> AS ?c)
                ?c a skos:Concept ;
                    skos:prefLabel ?label ;
                    skos:definition ?def ;
                    skos:inScheme ?cs .
                OPTIONAL {{
                    ?c rdfs:isDefinedBy ?defined .
                    ?defined a skos:ConceptScheme ;
                        skos:prefLabel ?defined_label .
                }}
                OPTIONAL {{
                    ?c ?prov_pred ?prov .
                    FILTER (?prov_pred IN (dcterms:provenance, dcterms:source, prov:wasDerivedFrom))
                }}
                ?cs a skos:ConceptScheme ;
                    skos:prefLabel ?cs_label .
                OPTIONAL {{
                    ?c skos:broader ?broader .
                    ?broader a skos:Concept ;
                        skos:prefLabel ?broader_label .
                }}
                OPTIONAL {{
                    ?c skos:narrower ?narrower .
                    ?narrower a skos:Concept ;
                        skos:prefLabel ?narrower_label .
                }}
            }}
        """
        )

        g = r.graph
        g.bind("dcterms", DCTERMS)
        g.bind("prov", PROV)
        g.bind("rdfs", RDFS)
        g.bind("skos", SKOS)

        return g

    def _render_vocpub_rdf(self) -> Response:
        """Renders the RDF representation of the vocpub profile for a concept"""
        g = self._generate_vocpub_rdf()
        return self._make_rdf_response(self.instance_uri, g)

    def _render_vocpub(self, template_context: Union[Dict, None]):
        """Renders the vocpub profile for a concept"""
        if self.mediatype == "text/html":
            return self._render_vocpub_html(template_context)
        else:  # all other formats are RDF
            return self._render_vocpub_rdf()

    def _generate_skos_rdf(self) -> Graph:
        r = self.concept.graph.query(
            f"""
            PREFIX skos: <{SKOS}>
            CONSTRUCT {{
                ?c ?c_pred ?c_o .
                ?cs ?cs_pred ?cs_o .
                ?broader ?broader_pred ?broader_o .
                ?narrower ?narrower_pred ?narrower_o .
            }}
            WHERE {{
                BIND (<{self.concept.uri}> AS ?c)
                ?c ?c_pred ?c_o ;
                    skos:inScheme ?cs .
                FILTER (STRSTARTS(STR(?c_pred), STR(skos:)))
                ?cs ?cs_pred ?cs_o .
                FILTER (STRSTARTS(STR(?cs_pred), STR(skos:)))
                OPTIONAL {{
                    ?c skos:broader ?broader .
                    ?broader ?broader_pred ?broader_o .
                    FILTER (STRSTARTS(STR(?broader_pred), STR(skos:)))
                }}
                OPTIONAL {{
                    ?c skos:narrower ?narrower .
                    ?narrower ?narrower_pred ?narrower_o .
                    FILTER (STRSTARTS(STR(?narrower_pred), STR(skos:)))
                }}
            }}
        """
        )

        g = r.graph
        g.bind("skos", SKOS)

        return g

    def _render_skos_rdf(self) -> Response:
        """Renders the RDF representation of the skos profile for a concept"""
        g = self._generate_skos_rdf()
        return self._make_rdf_response(g)

    def _render_skos(self):
        """Renders the skos profile for a concept"""
        return self._render_skos_rdf()

    def _render_vocpub_supplied(self):
        """Renders the vocpub_supplied profile for a concept"""
        return self._render_vocpub_rdf()

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
        elif self.profile == "vocpub":
            return self._render_vocpub(template_context)
        elif self.profile == "skos":
            return self._render_skos()
        elif self.profile == "vocpub_supplied":
            return self._render_vocpub_supplied()
        else:
            return None
