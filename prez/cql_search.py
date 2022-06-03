from typing import Optional
import re

from config import CQL_PROPS


class CQLSearch(object):
    def __init__(
        self,
        filter: str,
        datasets: str,
        collections: str,
        filter_lang: Optional[str] = None,
        filter_crs: Optional[str] = None,
    ) -> None:
        self.filter = filter
        self.datasets = datasets
        self.collections = collections
        self.filter_lang = filter_lang
        self.filter_crs = filter_crs
        self.query = ""

    def _parse_eq_ops(self, f: str) -> str:
        return re.sub(
            r'(\w+)\s?(<>|<=|>=|=|<|>)\s?(".+"|\d+(?:\.\d+)?)',
            lambda x: f'?{x.group(1)} {"!=" if x.group(2) == "<>" else x.group(2)} {x.group(3)}',
            f,
            flags=re.IGNORECASE,
        )

    def _parse_between(self, f: str) -> str:
        return re.sub(
            r"(\w+) between (\w+|\d+) and (\w+|\d+)",
            r"(?\1 >= \2 && ?\1 <= \3)",
            f,
            flags=re.IGNORECASE,
        )

    def _parse_or(self, f: str) -> str:
        return re.sub(r" or ", r" || ", f, flags=re.IGNORECASE)

    def _parse_and(self, f: str) -> str:
        return re.sub(r" and ", r" && ", f, flags=re.IGNORECASE)

    def _parse_like(self, f: str) -> str:
        return re.sub(
            r'(\w+) like (".+")', r'regex(?\1, \2, "i" )', f, flags=re.IGNORECASE
        )

    def _parse_is(self, f: str) -> str:
        return re.sub(
            r"(\w+) is (not )?null",
            lambda x: f'{"NOT " if x.group(2) is None else ""}EXISTS {{?f {CQL_PROPS[x.group(1)]["qname"]} ?{x.group(1)}}}',
            f,
            flags=re.IGNORECASE,
        )

    def _parse_in(self, f: str) -> str:
        return re.sub(
            r'(\w+) (in) (\((?:(?:".+"|\d+),\s?)*(?:".+"|\d+)\))',
            r"?\1 \2 \3",
            f,
            flags=re.IGNORECASE,
        )

    def generate_query(self) -> str:
        # cater for specifying datasets & not collections
        self.query = f"""
            ?d a dcat:Dataset ;
                dcterms:identifier ?d_id ;
                rdfs:member ?coll .
           
            BIND(STR(?d_id) AS ?d_id_str)
            VALUES ?d_id_str {{{" ".join([f'"{d.strip()}"' for d in self.datasets.split(',')])}}}
            BIND(DATATYPE(?d_id) AS ?d_id_dt)
            FILTER(?d_id_dt = xsd:token)

            ?coll a geo:FeatureCollection ;
                dcterms:identifier ?coll_id ;
                rdfs:member ?f .
            
            BIND(STR(?coll_id) AS ?coll_id_str)
            VALUES ?coll_id_str {{{" ".join([f'"{coll.strip()}"' for coll in self.collections.split(',')])}}}
            BIND(DATATYPE(?coll_id) AS ?coll_id_dt)
            FILTER(?coll_id_dt = xsd:token)

            ?f a geo:Feature .
        """

        self.filter = self._parse_eq_ops(self.filter)
        self.filter = self._parse_between(self.filter)
        self.filter = self._parse_or(self.filter)
        self.filter = self._parse_and(self.filter)
        self.filter = self._parse_like(self.filter)
        self.filter = self._parse_is(self.filter)
        self.filter = self._parse_in(self.filter)

        for prop in CQL_PROPS.keys():
            if f"?{prop}" in self.filter:
                # check for exists/is null to avoid inserting unnecessary triples
                # if the only reference of a prop is with EXISTS, then don't insert triple
                if len(re.findall(f"\?{prop}", self.filter)) > len(
                    re.findall(
                        f"EXISTS\s?{{\s?\?f {CQL_PROPS[prop]['qname']} \?{prop}",
                        self.filter,
                        flags=re.IGNORECASE,
                    )
                ):
                    self.query += f"\n?f {CQL_PROPS[prop]['qname']} ?{prop} ."

        self.filter = f"FILTER({self.filter})"
        self.query += f"\n{self.filter}"
        return self.query
