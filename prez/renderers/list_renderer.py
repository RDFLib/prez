from typing import Dict, Optional, Union, List
from abc import ABCMeta, abstractmethod

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from connegp import RDF_MEDIATYPES

from prez.renderers import Renderer
from prez.config import *

from prez.utils import templates


class ListRenderer(Renderer, metaclass=ABCMeta):
    def __init__(
        self,
        request: object,
        instance_uri: str,
        members: List[Dict],
        label: str,
        comment: str,
        page: int,
        per_page: int,
        member_count: int,
        instance_classes: list,
        general_class: str,
    ) -> None:

        super().__init__(request, instance_uri, instance_classes, general_class)

        if self.error is None:
            self.members = members
            self.label = label
            self.comment = comment
            self.member_count = member_count

            ceiling = lambda a, b: a // b + bool(a % b)
            # need a way to count the total no. of features (separate query?)
            last_page = ceiling(self.member_count, per_page)
            self.pages = {
                "first": 1,
                "prev": page - 1 if page > 1 else 1,
                "current": page,
                "next": page + 1 if page < last_page else last_page,
                "last": last_page,
                "member_count": self.member_count,
            }

    # pagination

    def _render_mem_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the members profiles using the 'mem.html' template"""
        _template_context = {
            "request": self.request,
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "members": self.members,
            "label": self.label,
            "comment": self.comment,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "mem.html", context=_template_context, headers=self.headers
        )

    def _render_mem_json(self) -> JSONResponse:
        """Renders the JSON representation of the members profile"""
        return JSONResponse(
            content={
                "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
                "members": self.members,
                "label": self.label,
                "comment": self.comment,
            },
            media_type="application/json",
            headers=self.headers,
        )

    def _generate_mem_rdf(self) -> Graph:
        g = Graph()

        # LDP = Namespace("http://www.w3.org/ns/ldp#")
        # g.bind("ldp", LDP)

        # XHV = Namespace("https://www.w3.org/1999/xhtml/vocab#")
        # g.bind("xhv", XHV)

        u = URIRef(self.instance_uri)
        g.add((u, RDF.type, RDF.Bag))
        g.add((u, RDFS.label, Literal(self.label)))
        g.add((u, RDFS.comment, Literal(self.comment, lang="en")))
        for member in self.members:
            member_uri = URIRef(member["uri"])
            g.add((u, RDFS.member, member_uri))
            g.add((member_uri, RDFS.label, Literal(member["title"])))

        return g

    def _render_mem_rdf(self) -> Response:
        """Renders the RDF representation of the members profile"""
        g = self._generate_mem_rdf()
        return self._make_rdf_response(self.instance_uri, g)

    def _render_mem(
        self, template_context: Union[Dict, None]
    ) -> Union[templates.TemplateResponse, Response, JSONResponse]:
        """Renders the members profile based on mediatype"""
        if self.mediatype == "text/html":
            return self._render_mem_html(template_context)
        elif self.mediatype in RDF_MEDIATYPES:
            return self._render_mem_rdf()
        else:  # application/json
            return self._render_mem_json()

    @abstractmethod
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
        # extra profiles go here
        else:
            return None
