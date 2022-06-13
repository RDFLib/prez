from typing import List, Dict, Optional

from prez.config import *
from prez.models import PrezModel


class VocPrezCollection(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        # str(SKOS.definition),
    ]
    hidden_props = [
        str(SKOS.member),
        str(DCTERMS.identifier),
        str(SDO.identifier),  # not being hidden
        str(SKOS.definition),
    ]

    def __init__(
        self, graph: Graph, id: Optional[str] = None, uri: Optional[str] = None
    ) -> None:
        super().__init__(graph)

        if id is None and uri is None:
            raise ValueError("Either an ID or a URI must be provided")

        query_by_id = f"""
                ?coll dcterms:identifier "{id}"^^xsd:token .
                BIND("{id}" AS ?id)
        """

        query_by_uri = f"""
                BIND (<{uri}> as ?coll)
                ?coll dcterms:identifier ?id .
        """

        r = self.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            PREFIX xsd: <{XSD}>
            
            SELECT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}
                
                ?coll a skos:Collection ;
                    rdfs:label|skos:prefLabel|dcterms:title ?title ;
                    skos:definition|dcterms:description ?desc .
                FILTER(lang(?title) = "" || lang(?title) = "en")
            }}
        """
        )

        result = r.bindings[0]
        self.uri = result["coll"]
        self.id = result["id"]
        self.title = result["title"]
        self.description = result["desc"]

    # override
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "properties": self._get_properties(),
            "concepts": self._get_concept_list(),
        }

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        other_props = []

        for prop in props_dict:
            if prop["value"] in VocPrezCollection.hidden_props:
                continue
            elif prop["value"] in VocPrezCollection.main_props:
                main_props.append(prop)
            else:
                other_props.append(prop)

        # sorts & combines into a single list
        properties.extend(main_props)
        properties.extend(other_props)

        return properties

    def _get_concept_list(self) -> List[Dict[str, str]]:
        concept_list = []
        r = self.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT *
            WHERE {{
                <{self.uri}> skos:member ?c .
                ?c rdfs:label|skos:prefLabel|dcterms:title ?label ;
                    skos:inScheme ?cs ;
                    dcterms:identifier ?id .
                FILTER(lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
                ?cs dcterms:identifier ?cs_id .
            }}
        """
        )

        for result in r.bindings:
            concept_list.append(
                {
                    "uri": result["c"],
                    "label": result["label"],
                    "id": result["id"],
                    "scheme_id": result["cs_id"],
                }
            )
        return sorted(concept_list, key=lambda c: c["label"])

    def get_concept_flat_list(self) -> List[Dict[str, str]]:
        concept_list = []
        r = self.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT ?c ?label
            WHERE {{
                <{self.uri}> skos:member ?c .
                ?c rdfs:label|skos:prefLabel|dcterms:title ?label .
                FILTER(lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
            }}
        """
        )

        for result in r.bindings:
            concept_list.append(
                {
                    "uri": result["c"],
                    "prefLabel": result["label"],
                }
            )
        return sorted(concept_list, key=lambda c: c["prefLabel"])
