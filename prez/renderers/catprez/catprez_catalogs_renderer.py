from typing import Dict, Optional, Union

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from connegp import MEDIATYPE_NAMES

from prez.renderers import ListRenderer
from prez.config import *
from prez.models.catprez import CatPrezCatalogs
from prez.utils import templates


class CatPrezCatalogsRenderer(ListRenderer):
    def __init__(
        self,
        request: object,
        scheme_list: CatPrezCatalogs,
        page: int,
        per_page: int,
        member_count: int,
    ) -> None:
        super().__init__(
            request,
            PREZ.Schemes,
            scheme_list.members,
            "Catalog list",
            "The dcat:Catalog instances delivered by this CatPrez system",
            page,
            per_page,
            member_count,
            DCAT.Catalog,
            DCAT.Catalog,
        )
        self.scheme_list = scheme_list

    def _render_dcat_html(self, template_context: Union[Dict, None]):
        """Renders the HTML representation of the DCAT profile for a dataset"""
        _template_context = {
            "request": self.request,
            "members": self.members,
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "pages": self.pages,
            "label": self.label,
            "comment": self.comment,
            "profiles": self.profile_details.available_profiles_dict,
            "default_profile": self.profile_details.default_profile,
            "mediatype_names": MEDIATYPE_NAMES,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "catprez/catprez_catalogs.html",
            context=_template_context,
            headers=self.headers,
        )

    def _generate_dcat_rdf(self) -> Graph:
        """Generates a Graph of the DCAT representation"""
        g = self._generate_mem_rdf()
        g.bind("dcat", DCAT)
        g.bind("dcterms", DCTERMS)
        for s in g.subjects(predicate=RDF.type, object=RDF.Bag):
            g.remove((s, RDF.type, RDF.Bag))
            g.add((s, RDF.type, DCAT.Catalog))

            for p, o in g.predicate_objects(subject=s):
                if p == RDFS.label:
                    g.remove((s, p, o))
                    g.add((s, DCTERMS.title, o))
                elif p == RDFS.comment:
                    g.remove((s, p, o))
                    g.add((s, DCTERMS.description, o))

            api = URIRef(self.instance_uri)
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
            g.add((sparql, RDF.type, DCAT.DataService))
            g.add((sparql, DCTERMS.title, Literal("System SPARQL Service")))
            g.add(
                (
                    sparql,
                    DCTERMS.description,
                    Literal(
                        "A SPARQL Protocol-compliant service that provides access "
                        "to all of this catalogue's information"
                    ),
                )
            )
            g.add((sparql, DCTERMS.type, URIRef("http://purl.org/dc/dcmitype/Service")))
            g.add((sparql, DCAT.endpointURL, sparql))

        for s, o in g.subject_objects(predicate=RDFS.member):
            g.remove((s, RDFS.member, o))
            g.add((o, RDF.type, DCAT.Dataset))
            g.add((s, DCAT.dataset, o))
            for p2, o2 in g.predicate_objects(subject=o):
                if p2 == RDFS.label:
                    g.remove((o, p2, o2))
                    g.add((o, DCTERMS.title, o2))
                elif p2 == RDFS.comment:
                    g.remove((o, p2, o2))
                    g.add((o, DCTERMS.description, o2))

        return g

    def _render_dcat_rdf(self):
        """Renders the RDF representation of the DCAT profile for a dataset"""
        g = self._generate_dcat_rdf()
        return self._make_rdf_response(self.instance_uri, g)

    def _render_dcat(self, template_context: Union[Dict, None]):
        if self.mediatype == "text/html":
            return self._render_dcat_html(template_context)
        else:  # all other formats are RDF
            return self._render_dcat_rdf()

    def _render_dd_json(self) -> JSONResponse:
        """Renders the json representation of the dd profile for a list of concept catalogs"""
        return JSONResponse(
            content=self.catalog_list.get_catalog_flat_list(),
            media_type="application/json",
            headers=self.headers,
        )

    def _render_dd(self):
        """Renders the dd profile for a list of concept catalogs"""
        return self._render_dd_json()

    def render(
        self,
        template_context: Optional[Dict] = None,
        alt_profiles_graph: Optional[Graph] = None,
    ) -> Union[
        PlainTextResponse, templates.TemplateResponse, Response, JSONResponse, None
    ]:
        if self.error is not None:
            return PlainTextResponse(self.error, status_code=400)
        elif self.profile == "mem":
            return self._render_mem(template_context)
        elif self.profile == "alt":
            return self._render_alt(template_context, alt_profiles_graph)
        elif self.profile == "dcat":
            return self._render_dcat(template_context)
        elif self.profile == "dd":
            return self._render_dd()
        else:
            return None
