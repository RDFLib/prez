from typing import List, Dict

from rdflib.namespace import DCTERMS, SKOS, RDF

from config import *
from models import PrezModel


class VocPrezDataset(PrezModel):
    # class attributes for property grouping & order
    main_props = [
        str(SKOS.definition),
        str(DCTERMS.creator),
        str(DCTERMS.created),
        str(DCTERMS.modified),
    ]

    def __init__(self, sparql_response: List) -> None:
        super().__init__(sparql_response, "dataset")

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
            elif uri in VocPrezDataset.main_props:
                main_properties.append(prop)
            else:
                other_properties.append(prop)
        # sort & add to properties
        self.properties.extend(
            sorted(
                main_properties,
                key=lambda p: self._sort_within_list(p, VocPrezDataset.main_props),
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
        }
