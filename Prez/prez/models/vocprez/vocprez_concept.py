from typing import List, Dict

from rdflib.namespace import DCTERMS, SKOS, RDF

from config import *
from models import PrezModel


class VocPrezConcept(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        str(SKOS.definition),
        str(DCTERMS.creator),
        str(DCTERMS.created),
        str(DCTERMS.modified),
    ]

    def __init__(self, sparql_response: List[Dict], broader_response: List[Dict], narrower_response: List[Dict]) -> None:
        super().__init__(sparql_response, "c")
        self.scheme = self._set_scheme(sparql_response)
        self.broader = self._set_broader_concepts(broader_response)
        self.narrower = self._set_narrower_concepts(narrower_response)

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
            elif uri == str(SKOS.inScheme) or uri == str(SKOS.topConceptOf):
                continue
            elif uri == str(SKOS.broader) or uri == str(SKOS.narrower):
                continue
            elif uri in VocPrezConcept.main_props:
                main_properties.append(prop)
            else:
                other_properties.append(prop)
        # sort & add to properties
        self.properties.extend(
            sorted(
                main_properties,
                key=lambda p: self._sort_within_list(p, VocPrezConcept.main_props),
            )
        )
        # for other, sort by predicate alphabetically
        self.properties.extend(sorted(other_properties, key=lambda p: p["prefix"]))

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "description": self.description,
            "uri": self.uri,
            "type": self.type,
            "properties": self.properties,
            "scheme": self.scheme,
            "broader": self.broader,
            "narrower": self.narrower
        }

    def _set_scheme(self, sparql_response: List[Dict]) -> Dict[str, str]:
        result = sparql_response[0]
        return {
            "uri": result["cs"]["value"],
            "id": result["cs_id"]["value"],
            "label": result["csLabel"]["value"],
        }
    
    def _set_broader_concepts(self, broader_response: List[Dict]) -> List[Dict]:
        broader = []
        for result in broader_response:
            broader.append({
                "uri": result["broader"]["value"],
                "id": result["id"]["value"],
                "scheme_id": result["cs_id"]["value"],
                "label": result["label"]["value"],
            })
        return broader
    
    def _set_narrower_concepts(self, narrower_response: List[Dict]) -> List[Dict]:
        narrower = []
        for result in narrower_response:
            narrower.append({
                "uri": result["narrower"]["value"],
                "id": result["id"]["value"],
                "scheme_id": result["cs_id"]["value"],
                "label": result["label"]["value"],
            })
        return narrower
