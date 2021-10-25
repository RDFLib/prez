from typing import List, Dict, Optional

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, SKOS

from config import *
from models import PrezModelConstructed


class VocPrezConceptConstructed(PrezModelConstructed):
    # class attributes for property grouping & order
    main_props = [
        SKOS.definition,
    ]

    hidden_props = []

    def __init__(
        self, graph: Graph, id: Optional[str] = None, uri: Optional[str] = None
    ) -> None:
        super().__init__(graph)

        if id is None and uri is None:
            raise ValueError("Either an ID or a URI must be provided")

        query_by_id = f"""
            ?c dcterms:identifier ?id .
            FILTER (STR(?id) = "{id}")
        """

        query_by_uri = f"""
            BIND (<{uri}> as ?c) 
            ?c dcterms:identifier ?id .
        """

        r = self.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}
                ?c a skos:Concept ;
                    rdfs:label|skos:prefLabel|dcterms:title ?title ;
                    skos:definition|dcterms:description ?desc ;
                    skos:inScheme ?cs .
                ?cs dcterms:identifier ?cs_id ;
                    skos:prefLabel ?cs_label .
            }}
        """
        )

        result = r.bindings[0]
        self.uri = result["c"]
        self.id = result["id"]
        self.title = result["title"]
        self.description = result["desc"]
        self.scheme = {
            "uri": result["cs"],
            "id": result["cs_id"],
            "title": result["cs_label"],
        }

    # override
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "properties": self._get_properties(),
            "scheme": self.scheme,
        }

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props_dict()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        other_props = []

        for uri, prop in props_dict.items():
            if uri in VocPrezConceptConstructed.hidden_props:
                continue
            elif uri in VocPrezConceptConstructed.main_props:
                main_props.append(prop)
            else:
                other_props.append(prop)

        properties.extend(
            sorted(
                main_props,
                key=lambda p: self._sort_within_list(
                    p, VocPrezConceptConstructed.main_props
                ),
            )
        )
        properties.extend(other_props)

        return properties
