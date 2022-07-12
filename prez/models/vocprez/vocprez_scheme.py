from typing import List, Dict, Optional

from prez.config import *
from prez.models import PrezModel


class VocPrezScheme(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        # str(SKOS.definition),
        str(DCTERMS.creator),
        str(DCTERMS.created),
        str(DCTERMS.modified),
    ]
    hidden_props = [
        str(RDFS.seeAlso),
        str(SKOS.hasTopConcept),
        str(DCTERMS.identifier),
        str(SKOS.definition),
    ]

    def __init__(
        self, graph: Graph, id: Optional[str] = None, uri: Optional[str] = None
    ) -> None:
        super().__init__(graph)

        if id is None and uri is None:
            raise ValueError("Either an ID or a URI must be provided")

        query_by_id = f"""
                ?cs dcterms:identifier "{id}"^^xsd:token .
                BIND("{id}" AS ?id)
        """

        query_by_uri = f"""
                BIND (<{uri}> as ?cs)
                ?cs dcterms:identifier ?id .
        """

        qx = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            PREFIX xsd: <{XSD}>
            
            SELECT *
            WHERE {{
                {query_by_id if id is not None else query_by_uri}
                
                ?cs a skos:ConceptScheme ;
                    rdfs:label|skos:prefLabel|dcterms:title ?title ;
                    skos:definition|dcterms:description ?desc .
                FILTER(lang(?title) = "" || lang(?title) = "en")
            }}
            """

        r = self.graph.query(qx)

        result = r.bindings[0]
        self.uri = result["cs"]
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
            "concepts": self._get_concept_hierarchy(),
        }

    def get_concept_flat_list(self) -> List[Dict[str, str]]:
        r = self.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT ?c ?label ?b
            WHERE {{
                ?c skos:inScheme <{self.uri}> ;
                    rdfs:label|skos:prefLabel|dcterms:title ?label .
                OPTIONAL {{
                    {{ ?c skos:broader ?b }}
                    UNION
                    {{ ?b skos:narrower ?c }}
                }}
                FILTER (lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
            }}
            """
        )

        last_concept = {}
        concept_list = []

        for result in r.bindings:
            if result["c"] != last_concept.get("iri"):
                if last_concept != {}:
                    concept_list.append(last_concept)

                last_concept = {
                    "iri": result["c"],
                    "prefLabel": result["label"],
                    "broader": [result["b"]] if result.get("b") else [],
                }
            else:
                if result.get("b"):
                    last_concept["broader"].append(result["b"])
        concept_list.append(last_concept)

        return sorted(concept_list, key=lambda c: c["prefLabel"])

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        other_props = []

        for prop in props_dict:
            if prop["value"] in VocPrezScheme.hidden_props:
                continue
            elif prop["value"] in VocPrezScheme.main_props:
                main_props.append(prop)
            else:
                other_props.append(prop)

        # sorts & combines into a single list
        properties.extend(main_props)
        properties.extend(other_props)

        return properties

    def _get_concept_hierarchy(self) -> Dict:
        r = self.graph.query(
            f"""
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT *
            WHERE {{
                <{self.uri}> skos:hasTopConcept ?tc .
            }}
        """
        )

        top_concept_list = [result["tc"] for result in r.bindings]

        r = self.graph.query(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT *
            WHERE {{
                ?c skos:inScheme <{self.uri}> ;
                    a skos:Concept ;
                    skos:prefLabel ?label ;
                    dcterms:identifier ?id .
                FILTER (LANG(?label) = "en")
                OPTIONAL {{
                    {{ ?c skos:narrower ?narrower }}
                    UNION 
                    {{ ?narrower skos:broader ?c }}
                }}
            }}
        """
        )

        concepts_dict = {}
        for result in r.bindings:
            if concepts_dict.get(result["c"]):
                if result.get("narrower"):
                    concepts_dict[result["c"]]["narrower"].append(result["narrower"])
            else:
                concepts_dict[result["c"]] = {
                    "uri": result["c"],
                    "label": result["label"],
                    "id": result["id"],
                    "narrower": [result["narrower"]] if result.get("narrower") else [],
                }

        hierarchy = {}

        def recursive_narrow(concept_list, concepts_dict, hierarchy):
            for uri in concept_list:
                hierarchy[uri] = {
                    "uri": concepts_dict[uri]["uri"],
                    "label": concepts_dict[uri]["label"],
                    "id": concepts_dict[uri]["id"],
                    "narrower": {},
                }
                recursive_narrow(
                    concepts_dict[uri]["narrower"],
                    concepts_dict,
                    hierarchy[uri]["narrower"],
                )

        recursive_narrow(top_concept_list, concepts_dict, hierarchy)

        return hierarchy
