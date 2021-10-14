from typing import List, Dict

from rdflib.namespace import DCTERMS, SKOS, RDF

from config import *
from models import PrezModel


class VocPrezScheme(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        str(SKOS.definition),
        str(DCTERMS.creator),
        str(DCTERMS.created),
        str(DCTERMS.modified),
    ]

    def __init__(self, sparql_response: List, concept_response: List) -> None:
        self.top_concepts = []
        super().__init__(sparql_response, "cs")
        self.concepts = self._set_concept_hierarchy(concept_response)

    def _set_props(self, props_dict: Dict[str, Dict]) -> None:
        """Sets the transformed SPARQL results into appropriate attributes according to class-specific property groups"""
        main_properties = []
        other_properties = []
        for uri, prop in props_dict.items():
            if uri == str(DCTERMS.description):
                self.description = prop
            elif uri == str(DCTERMS.title):
                self.title = prop
            elif uri == str(RDF.type):
                self.type = prop
            elif uri == str(DCTERMS.identifier):
                self.id = prop
            elif uri in str(SKOS.hasTopConcept):
                self.top_concepts = prop
            elif uri in VocPrezScheme.main_props:
                main_properties.append(prop)
            else:
                other_properties.append(prop)
        # sort & add to properties
        self.properties.extend(
            sorted(
                main_properties,
                key=lambda p: self._sort_within_list(p, VocPrezScheme.main_props),
            )
        )
        # for other, sort by predicate alphabetically
        self.properties.extend(sorted(other_properties, key=lambda p: p["prefix"]))

    def to_dict(self):
        return {
            "title": self.title,
            "description": self.description,
            "uri": self.uri,
            "type": self.type,
            "properties": self.properties,
            "id": self.id,
            "concepts": self.concepts,
        }

    def _set_concept_hierarchy(self, results):
        hierarchy = {}

        # reformat results
        results_dict = {}
        for result in results:
            uri = result["c"]["value"]
            if uri not in results_dict.keys():
                results_dict[uri] = {
                    "label": result["label"]["value"],
                    "id": result["id"]["value"],
                    "narrower": [],
                    "broader": [],
                }
            if result.get("narrower") is not None:
                results_dict[uri]["narrower"].append(result["narrower"]["value"])
            if result.get("broader") is not None:
                results_dict[uri]["broader"].append(result["broader"]["value"])

        # top level concepts
        for uri, props in results_dict.items():
            if uri in [u["value"] for u in self.top_concepts["objects"]]:
                hierarchy[uri] = {
                    "label": props["label"],
                    "id": props["id"],
                    "children": {},
                }

        # build hierarchy
        self._get_concept_children(hierarchy, results_dict)

        return hierarchy

    def _get_concept_children(self, children_dict: Dict, results_dict: Dict):
        for uri, props in children_dict.items():
            c = results_dict[uri]
            # narrower
            for narrower in c["narrower"]:
                n = results_dict[narrower]
                props["children"][narrower] = {
                    "label": n["label"],
                    "id": n["id"],
                    "children": {},
                }
            # broader
            for concept, concept_props in results_dict.items():
                if (
                    uri in concept_props["broader"]
                    and concept not in props["children"].keys()
                ):
                    props["children"][concept] = {
                        "label": concept_props["label"],
                        "id": concept_props["id"],
                        "children": {},
                    }
            self._get_concept_children(props["children"], results_dict)
