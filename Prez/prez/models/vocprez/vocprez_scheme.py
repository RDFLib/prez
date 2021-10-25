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

    def __init__(
        self, sparql_response: List[Dict], concept_response: List[Dict]
    ) -> None:
        self.top_concepts = []
        super().__init__(sparql_response, "cs")
        self.concepts = self._set_concept_hierarchy(concept_response)
        self.concept_list = self._set_concept_flat_list(concept_response)

    def _set_props(self, props_dict: Dict[str, Dict]) -> None:
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
            elif uri == str(RDFS.seeAlso):
                continue
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
        # self.properties.extend(sorted(other_properties, key=lambda p: p["label"]))
        self.properties.extend(other_properties)

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

    def _set_concept_flat_list(self, results: List[Dict]) -> List[Dict[str, str]]:
        """Creates a flat list of Concepts ordered by prefLabel"""
        # use set to guarantee uniqueness of concepts
        # (duplicates appear as the concept query has narrower/broader info)
        concept_set = set()
        for result in results:
            concept_set.add(
                (result["c"]["value"], result["label"]["value"])
            )
        concept_list = [{"uri": c[0], "prefLabel": c[1]} for c in concept_set]
        return sorted(concept_list, key=lambda c: c["prefLabel"])

    def _set_concept_hierarchy(self, results: List[Dict]) -> Dict[str, Dict]:
        """Sets the concept hierarchy as a nested dictionary"""
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

    def _get_concept_children(
        self, children_dict: Dict[str, Dict], results_dict: Dict[str, Dict]
    ) -> None:
        """Recursively sets children for each child by checking narrower & broader"""
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
