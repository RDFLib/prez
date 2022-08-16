from abc import ABCMeta, abstractmethod
from typing import Dict, Optional, Union

from connegp import Connegp, RDF_MEDIATYPES, RDF_SERIALIZER_TYPES_MAP
from fastapi.responses import Response, JSONResponse, PlainTextResponse
from rdflib import URIRef

from prez.config import *
from prez.profiles.generate_profiles import ProfileDetails
from prez.utils import templates


class Renderer(object, metaclass=ABCMeta):
    """Abstract class containing base logic for conditionally rendering based on profile & mediatype"""

    def __init__(
        self,
        request: object,
        instance_uri: str,
        instance_classes,
        general_class: URIRef = OWL.Class,
    ) -> None:
        self.error = None
        self.request = request
        self.instance_uri = instance_uri
        self.instance_classes = instance_classes
        self.general_class = general_class
        self.profile_details = ProfileDetails(
            self.instance_uri, self.instance_classes, self.general_class
        )

        connegp = Connegp(
            request,
            self.profile_details.available_profiles_dict,
            self.profile_details.default_profile,
        )
        self.profile = connegp.profile
        self.mediatype = connegp.mediatype
        self.profiles_requested = connegp.profiles_requested
        self.mediatypes_requested = connegp.mediatypes_requested

        # make headers
        if self.error is None:
            self.headers = {
                "Link": f'<{self.profile_details.profiles_dict[self.profile].uri}>; rel="profile"',
                "Content-Type": self.mediatype,
                "Access-Control-Allow-Origin": "*",
            }
            self.headers["Link"] += ", " + self._make_header_link_tokens()
            self.headers["Link"] += ", " + self._make_header_link_list_profiles()

    def _make_header_link_tokens(self) -> str:
        """Creates the Link header tokens for the supported profiles"""
        individual_links = []
        link_header_template = '<http://www.w3.org/ns/dx/prof/Profile>; rel="type"; token="{}"; anchor=<{}>, '

        for token, profile in self.profile_details.profiles_dict.items():
            individual_links.append(link_header_template.format(token, profile.uri))

        return "".join(individual_links).rstrip(", ")

    def _make_header_link_list_profiles(self) -> str:
        """Creates the Link header URIs for each possible profile representation"""
        individual_links = []
        for token, profile in self.profile_details.profiles_dict.items():
            # create an individual Link statement per Media Type
            for mediatype in profile.mediatypes:
                # set the rel="self" just for this profile & mediatype
                if mediatype != "_internal":
                    if (
                        token == self.profile_details.default_profile
                        and mediatype
                        == self.profile_details.profiles_dict[
                            self.profile
                        ].default_mediatype
                    ):
                        rel = "self"
                    else:
                        rel = "alternate"

                    individual_links.append(
                        '<{}?_profile={}&_mediatype={}>; rel="{}"; type="{}"; profile="{}", '.format(
                            self.instance_uri,
                            token,
                            mediatype,
                            rel,
                            mediatype,
                            profile.uri,
                        )
                    )

        # append to, or create, Link header
        return "".join(individual_links).rstrip(", ")

    def _make_rdf_response(self, item_uri, graph: Graph) -> Response:
        """Creates an RDF response from a Graph"""
        serial_mediatype = RDF_SERIALIZER_TYPES_MAP[self.mediatype]

        # remove labels from the graph
        query = f"""
        PREFIX skos: <{SKOS}>
        CONSTRUCT {{
            <{str(item_uri)}> ?p ?o .
            ?o ?p2 ?o2 .
            ?coll skos:member <{str(item_uri)}> .

            ?x rdfs:member <{str(item_uri)}> .
            ?y rdfs:member ?x .
        }}
        WHERE {{
            <{str(item_uri)}> ?p ?o .
            # Blank Nodes

            OPTIONAL {{
                ?o ?p2 ?o2 .
                FILTER(ISBLANK(?o))
            }}

            # VocPrez
            OPTIONAL {{
                ?coll skos:member <{str(item_uri)}> .
            }}

            # SpacePrez
            OPTIONAL {{
                ?x rdfs:member <{str(item_uri)}> .

                OPTIONAL {{
                    ?y rdfs:member ?x .
                }}
            }}
        }}
        """
        filtered_g = Graph(namespace_manager=graph.namespace_manager)
        filtered_g += graph.query(query).graph

        filtered_g = graph
        response_text = filtered_g.serialize(format=serial_mediatype, encoding="utf-8")

        # destroy the triples in the triplestore, then delete the triplestore
        # this helps to prevent a memory leak in rdflib
        graph.store.remove((None, None, None))
        graph.destroy({})
        del graph
        return Response(response_text, media_type=self.mediatype)

    def _render_alt_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the alternate profiles using the 'alt.html' template"""
        _template_context = {
            "request": self.request,
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "profiles": self.profile_details.available_profiles_dict,
            "default_profile": self.profile_details.default_profile,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "alt.html", context=_template_context, headers=self.headers
        )

    def _render_alt_json(self) -> JSONResponse:
        """Renders the JSON representation of the alternate profiles"""
        return JSONResponse(
            content={
                "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
                "profiles": list(self.profile_details.available_profiles_dict.keys()),
                "default_profile": self.profile_details.default_profile,
            },
            media_type="application/json",
            headers=self.headers,
        )

    def _render_alt(
        self, template_context: Union[Dict, None], alt_profiles_graph: Graph
    ) -> Union[templates.TemplateResponse, Response, JSONResponse]:
        """Renders the alternate profiles based on mediatype"""
        if self.mediatype == "text/html":
            return self._render_alt_html(template_context)
        elif self.mediatype in RDF_MEDIATYPES:
            response_text = alt_profiles_graph.serialize(format=self.mediatype)
            return Response(response_text, media_type=self.mediatype)
        else:  # application/json
            return self._render_alt_json()

    @abstractmethod
    def render(
        self,
        template_context: Optional[Dict] = None,
        alt_profiles_graph: Optional[Graph] = None,
    ) -> Union[
        PlainTextResponse, templates.TemplateResponse, Response, JSONResponse, None
    ]:
        """Renders this object based on a requested profile & mediatype"""
        if self.error is not None:
            return PlainTextResponse(self.error, status_code=400)
        elif self.profile == "alt":
            return self._render_alt(template_context, alt_profiles_graph)
        # extra profiles go here
        else:
            return None
