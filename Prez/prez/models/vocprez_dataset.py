from typing import List, Dict

from rdflib.namespace import DCTERMS, SKOS, RDF

from config import *


class VocPrezDataset(object):
    # class attributes for property grouping & order
    main_props = [
        str(SKOS.definition),
        str(DCTERMS.creator),
        str(DCTERMS.created),
        str(DCTERMS.modified),
    ]

    def __init__(self, sparql_response: List) -> None:
        self.properties = []
        self.title = None
        self.description = None
        self.uri = ""
        self.type = None
        props = self._get_props(sparql_response)
        self._set_props(props)

    def _get_prefix(self, uri: str):
        """Creates a predicate prefix"""
        for n in NAMESPACE_PREFIXES.keys():
            if uri.startswith(n):
                return NAMESPACE_PREFIXES[n] + ":" + uri.split(n)[-1]
        # else can't find match, return None
        return None

    def _get_props(self, sparql_response: List[Dict]):
        """Transforms the SPARQL response into dicts containing prefixes & labels"""
        results = []
        for result in sparql_response:
            r = {
                "p1": None,
                "p1Label": None,
                "p1Prefix": None,
                "o1": None,
                "o1Label": None,
                "o1Prefix": None,
            }
            for k, v in result.items():
                if k == "dataset":
                    self.uri = v["value"]
                elif k == "p1":
                    r["p1"] = v["value"]
                    if v["type"] == "uri":
                        r["p1Prefix"] = self._get_prefix(v["value"])
                elif k == "o1":
                    r["o1"] = v["value"]
                    if v["type"] == "uri":
                        r["o1Prefix"] = self._get_prefix(v["value"])
                elif k == "p1Label":
                    r["p1Label"] = v["value"]
                elif k == "o1Label":
                    r["o1Label"] = v["value"]
            results.append(r)
        return results

    def _set_props(self, props: List):
        """Sets the transformed SPARQL results into appropriate attributes according to class-specific property groups"""
        main_properties = []
        other_properties = []
        for prop in props:
            if prop["p1"] == str(DCTERMS.description):
                self.description = prop
            elif prop["p1"] == str(DCTERMS.title):
                self.title = prop
            elif prop["p1"] == str(RDF.type):
                self.type = prop
            elif prop["p1"] in VocPrezDataset.main_props:
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
        self.properties.extend(sorted(other_properties, key=lambda p: p["p1Prefix"]))

    def _sort_within_list(self, prop: Dict, prop_list: List):
        """Ensures props are sorted in-order within class-specific property groups"""
        if prop["p1"] in prop_list:
            return prop_list.index(prop["p1"])
        else:
            return len(prop_list)

    def to_dict(self):
        return {
            "title": self.title,
            "description": self.description,
            "uri": self.uri,
            "type": self.type,
            "properties": self.properties,
        }
