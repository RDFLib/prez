from abc import ABCMeta, abstractmethod
from typing import Dict, List, Union
import re

from rdflib import Graph, URIRef
from rdflib.namespace import RDFS


class PrezModel(object, metaclass=ABCMeta):
    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    @abstractmethod
    def to_dict(self) -> Dict:
        pass

    @abstractmethod
    def _get_properties(self) -> Dict:
        pass

    def _get_props_dict(self) -> Dict:
        r = self.graph.query(
            f"""
            PREFIX rdfs: <{RDFS}>
            SELECT DISTINCT *
            WHERE {{
                <{self.uri}> ?p ?o .
                BIND(DATATYPE(?o) AS ?datatype)
                BIND(LANG(?o) AS ?lang)
                OPTIONAL {{
                    ?p rdfs:label ?pLabel .
                    BIND(DATATYPE(?pLabel) AS ?pLabelDatatype)
                    BIND(LANG(?pLabel) AS ?pLabelLang)
                }}
                OPTIONAL {{
                    ?o rdfs:label ?oLabel .
                    BIND(DATATYPE(?oLabel) AS ?oLabelDatatype)
                    BIND(LANG(?oLabel) AS ?oLabelLang)
                }}
            }}
        """
        )

        # group objects with the same predicate
        props_dict = {}
        for result in r.bindings:
            obj = {
                "value": result["o"],
                "prefix": self._get_prefix(result["o"]),
                "label": result.get("oLabel"),
                "datatype": result.get("datatype"),
                "datatypePrefix": self._get_prefix(result.get("datatype")),
                "lang": result.get("lang"),
                "labelDatatype": result.get("oLabelDatatype"),
                "labelDatatypePrefix": self._get_prefix(result.get("oLabelDatatype")),
                "labelLang": result.get("oLabelLang"),
            }
            if props_dict.get(result["p"]):
                props_dict[result["p"]]["objects"].append(obj)
            else:
                props_dict[result["p"]] = {
                    "uri": result["p"],
                    "prefix": self._get_prefix(result["p"]),
                    "label": result.get("pLabel"),
                    "labelDatatype": result.get("pLabelDatatype"),
                    "labelDatatypePrefix": self._get_prefix(result.get("pLabelDatatype")),
                    "labelLang": result.get("pLabelLang"),
                    "objects": [obj],
                }
        return props_dict

    def _sort_within_list(self, prop: Dict, prop_list: List[str]) -> int:
        """Ensures props are sorted in-order within class-specific property groups"""
        if prop["uri"] in prop_list:
            return prop_list.index(prop["uri"])
        else:
            return len(prop_list)

    def _get_prefix(self, var) -> Union[str, None]:
        if isinstance(var, URIRef):
            prefix = var.n3(self.graph.namespace_manager)
            if re.match("<.+>", prefix):  # IRI, not a prefix
                return None
            else:
                return prefix
        else:
            return None
