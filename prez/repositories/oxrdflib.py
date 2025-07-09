import logging
from typing import Any

from fastapi.concurrency import run_in_threadpool
from pyoxigraph import Store, DefaultGraph, Quad
from oxrdflib._converter import to_ox
from rdflib import BNode, Graph, Literal, Namespace, URIRef

from prez.repositories.base import Repo

PREZ = Namespace("https://prez.dev/")

log = logging.getLogger(__name__)


class OxrdflibRepo(Repo):
    def __init__(self, oxrdflib_graph: Graph):
        self.oxrdflib_graph = oxrdflib_graph

    def _sync_rdf_query_to_rdflib_graph(
        self, query: str, into_graph: Graph | None = None
    ) -> Graph:
        # TODO, replace this rdflib sparql query with the
        # equivalent pyoxigraph query + results handling
        results = self.oxrdflib_graph.query(query)
        if into_graph is None:
            return results.graph
        else:
            if results.graph is None:
                return into_graph
            into_graph += results.graph
            return into_graph

    def _sync_rdf_query_to_oxigraph_store(
        self, query: str, into_store: Store | None = None
    ) -> Store:
        # TODO, replace this rdflib sparql query with the
        # equivalent pyoxigraph query + results handling
        results = self.oxrdflib_graph.query(query)
        if into_store is None:
            store = Store()
        else:
            store = into_store
        if results.graph is None:
            return store
        default = DefaultGraph()
        store.bulk_extend(
              Quad(to_ox(t.subject), to_ox(t.predicate), to_ox(t.object), default)
              for t in results.graph.triples((None, None, None))
            )
        return store

    def _sync_tabular_query_to_table(
        self, query: str, context: URIRef | None = None
    ) -> tuple[URIRef | None, list[dict[str, Any]]]:
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

    async def rdf_query_to_rdflib_graph(
        self, query: str, into_graph: Graph | None = None
    ) -> Graph:
        return await run_in_threadpool(
            self._sync_rdf_query_to_rdflib_graph, query, into_graph
        )

    async def rdf_query_to_oxigraph_store(
        self, query: str, into_store: Store | None = None
    ) -> Store:
        return await run_in_threadpool(
            self._sync_rdf_query_to_oxigraph_store, query, into_store
        )

    async def tabular_query_to_table(
        self, query: str, context: URIRef | None = None
    ) -> tuple[URIRef | None, list[dict[str, Any]]]:
        return await run_in_threadpool(
            self._sync_tabular_query_to_table, query, context
        )

    def _str_type_for_rdflib_type(self, instance):
        map = {URIRef: "uri", BNode: "bnode", Literal: "literal"}
        return map[type(instance)]
