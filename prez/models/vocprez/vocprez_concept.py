from typing import List, Dict, Optional

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, SKOS

from config import *
from models import PrezModel


class VocPrezConcept(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        SKOS.definition,
    ]

    hidden_props = [
        SKOS.semanticRelation,
        SKOS.broaderTransitive,
        SKOS.narrowerTransitive,
        DCTERMS.identifier,
        SDO.identifier,
        SKOS.inScheme,
        SKOS.topConceptOf,
        SKOS.broader,
        SKOS.narrower,
    ]

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
            "broader": self._get_broader_concepts(),
            "narrower": self._get_narrower_concepts(),
        }

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props_dict()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        other_props = []

        for uri, prop in props_dict.items():
            if uri in VocPrezConcept.hidden_props:
                continue
            elif uri in VocPrezConcept.main_props:
                main_props.append(prop)
            else:
                other_props.append(prop)

        properties.extend(
            sorted(
                main_props,
                key=lambda p: self._sort_within_list(
                    p, VocPrezConcept.main_props
                ),
            )
        )
        properties.extend(other_props)

        return properties
    
    def _get_broader_concepts(self) -> List[Dict]:
        broader = []
        r = self.graph.query(f"""
            SELECT DISTINCT *
            WHERE {{
                <{self.uri}> skos:broader ?broader .
                ?broader dcterms:identifier ?id ;
                    rdfs:label|skos:prefLabel|dcterms:title ?label ;
                    skos:inScheme/dcterms:identifier ?cs_id .
            }}
        """)

        for result in r.bindings:
            broader.append(
                {
                    "uri": result["broader"],
                    "label": result["label"],
                    "id": result["id"],
                    "scheme_id": result["cs_id"],
                }
            )
        return sorted(broader, key=lambda c: c["label"])

    def _get_narrower_concepts(self) -> List[Dict]:
        narrower = []
        r = self.graph.query(f"""
            SELECT DISTINCT *
            WHERE {{
                <{self.uri}> skos:narrower ?narrower .
                ?narrower dcterms:identifier ?id ;
                    rdfs:label|skos:prefLabel|dcterms:title ?label ;
                    skos:inScheme/dcterms:identifier ?cs_id .
            }}
        """)

        for result in r.bindings:
            narrower.append(
                {
                    "uri": result["narrower"],
                    "label": result["label"],
                    "id": result["id"],
                    "scheme_id": result["cs_id"],
                }
            )
        return sorted(narrower, key=lambda c: c["label"])
