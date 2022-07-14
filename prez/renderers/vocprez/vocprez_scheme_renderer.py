import csv
from io import StringIO

from connegp import MEDIATYPE_NAMES
from fastapi.responses import Response, JSONResponse, PlainTextResponse
from typing import Dict, Optional, Union

from prez.config import *
from prez.models.vocprez import VocPrezScheme
from prez.renderers import Renderer
from prez.services.vocprez_service import get_scheme_or_collection_uri
from prez.utils import templates


class VocPrezSchemeRenderer(Renderer):
    def __init__(
        self,
        request: object,
    ) -> None:
        (self.scheme_id, self.scheme_uri) = get_scheme_or_collection_uri(
            "ConceptScheme",
            request.path_params.get("scheme_id"),
            request.query_params.get("uri"),
        )
        super().__init__(
            request,
            self.scheme_uri,
            SKOS.ConceptScheme,
            SKOS.ConceptScheme,
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
        return self._make_rdf_response(self.instance_uri, g)

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

    def _render_dd_csv(self) -> PlainTextResponse:
        """Renders the CSV representation of the dd profile for a scheme"""
        data = self.scheme.get_concept_flat_list()
        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow(["ConceptIRI", "PrefLabel", "Broader"])
        for c in data:
            writer.writerow(
                [c["iri"], c["prefLabel"], "\n".join([b for b in c["broader"]])]
            )

        return PlainTextResponse(
            content=output.getvalue(),
            media_type="test/csv",
            headers=self.headers,
        )

    def _render_dd(self):
        """Renders the dd profile for a scheme"""
        if self.mediatype == "text/csv":
            return self._render_dd_csv()
        else:
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
        return self._make_rdf_response(self.instance_uri, g)

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
            "profiles": self.profile_details.available_profiles_dict,
            "default_profile": self.profile_details.default_profile,
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
