import logging

from fastapi.concurrency import run_in_threadpool
from rdflib import Namespace, Graph, URIRef, Literal, BNode

from prez.repositories.base import Repo

PREZ = Namespace("https://prez.dev/")

log = logging.getLogger(__name__)


class OxrdflibRepo(Repo):
    def __init__(self, oxrdflib_graph: Graph):
        self.oxrdflib_graph = oxrdflib_graph

    def _sync_rdf_query_to_graph(self, query: str) -> Graph:
        results = self.oxrdflib_graph.query(query)
        return results.graph

    def _sync_tabular_query_to_table(self, query: str, context: URIRef = None):
        results = self.oxrdflib_graph.query(query)
        reformatted_results = []
        for result in results:
            reformatted_result = {}
            for var in results.vars:
                binding = result[var]
                if binding:
                    str_type = self._str_type_for_rdflib_type(binding)
                    reformatted_result[str(var)] = {"type": str_type, "value": binding}
            reformatted_results.append(reformatted_result)
        return context, reformatted_results

    async def rdf_query_to_graph(self, query: str) -> Graph:
        return await run_in_threadpool(self._sync_rdf_query_to_graph, query)

    async def tabular_query_to_table(self, query: str, context: URIRef = None):
        return await run_in_threadpool(
            self._sync_tabular_query_to_table, query, context
        )

    def _str_type_for_rdflib_type(self, instance):
        map = {URIRef: "uri", BNode: "bnode", Literal: "literal"}
        return map[type(instance)]
