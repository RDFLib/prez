from abc import ABCMeta, abstractmethod
from typing import Union, List, Dict

from config import *


class PrezModel(object, metaclass=ABCMeta):
    def __init__(self, sparql_response: List[Dict], uri_var: str) -> None:
        self.properties = []
        self.title = None
        self.description = None
        self.uri = ""
        self.type = None
        self.id = ""
        props = self._get_props(sparql_response, uri_var)
        props_transformed = self._transform_props(props)
        self._set_props(props_transformed)

    def _get_prefix(self, uri: str) -> Union[str, None]:
        """Creates a predicate prefix"""
        for n in NAMESPACE_PREFIXES.keys():
            if uri.startswith(n):
                return NAMESPACE_PREFIXES[n] + ":" + uri.split(n)[-1]
        # else can't find match, return None
        return None

    def _get_props(self, sparql_response: List[Dict], uri_var: str) -> List[Dict]:
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
                if k == uri_var:
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

    def _transform_props(self, props: List) -> Dict[str, Dict]:
        """Groups objects with the same predicate"""
        props_dict = {}
        for prop in props:
            obj = {
                "value": prop["o1"],
                "prefix": prop["o1Prefix"],
                "label": prop["o1Label"],
            }
            if props_dict.get(prop["p1"]):
                props_dict[prop["p1"]]["objects"].append(obj)
            else:
                props_dict[prop["p1"]] = {
                    "uri": prop["p1"],
                    "prefix": prop["p1Prefix"],
                    "label": prop["p1Label"],
                    "objects": [obj],
                }
        return props_dict

    def _sort_within_list(self, prop: Dict, prop_list: List[str]) -> int:
        """Ensures props are sorted in-order within class-specific property groups"""
        if prop["uri"] in prop_list:
            return prop_list.index(prop["uri"])
        else:
            return len(prop_list)

    @abstractmethod
    def _set_props(self, props_dict: Dict[str, Dict]) -> None:
        """Sets the transformed SPARQL results into appropriate attributes according to class-specific property groups"""
        other_properties = []
        for uri, prop in props_dict.items():
            if uri == str(DCTERMS.description):
                self.description = prop
            elif uri == str(DCTERMS.title):
                self.title = prop
            elif uri == str(RDF.type):
                self.type = prop
            # custom stuff goes here
            else:
                other_properties.append(prop)
        # sort & add to properties
        # for other, sort by predicate alphabetically
        self.properties.extend(sorted(other_properties, key=lambda p: p["prefix"]))

    @abstractmethod
    def to_dict(self) -> Dict:
        "Returns a dictionary representation of the object for use in a template"
        return {
            "title": self.title,
            "description": self.description,
            "uri": self.uri,
            "type": self.type,
            "properties": self.properties,
        }
