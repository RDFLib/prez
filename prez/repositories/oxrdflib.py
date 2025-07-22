import logging
from typing import Any

from fastapi.concurrency import run_in_threadpool
from threading import Lock
from pyoxigraph import Store, DefaultGraph, Quad
from oxrdflib._converter import to_ox
from rdflib import BNode, Graph, Literal, Namespace, URIRef

from prez.repositories.base import Repo

PREZ = Namespace("https://prez.dev/")

log = logging.getLogger(__name__)


class OxrdflibRepo(Repo):
    def __init__(self, oxrdflib_graph: Graph):
        self.oxrdflib_graph = oxrdflib_graph
        self.into_store_write_locks = {}

    def _sync_rdf_query_to_rdflib_graph(
        self, query: str, into_graph: Graph | None = None
    ) -> Graph:
        # TODO, replace this rdflib sparql query with the
        # equivalent pyoxigraph query + results handling
        results = self.oxrdflib_graph.query(query)
        if into_graph is None:
            return results.graph
        if results.graph is None:
           return into_graph
        graph_lock = self.into_store_write_locks.get(id(into_graph), None)
        if graph_lock is not None:
            graph_lock.acquire()
        try:
            into_graph += results.graph
        finally:
            if graph_lock is not None:
                graph_lock.release()
        return into_graph

    def _sync_rdf_query_to_oxigraph_store(
        self, query: str, into_store: Store | None = None
    ) -> Store:
        # TODO, replace this rdflib sparql query with the
        # equivalent pyoxigraph query + results handling
        results = self.oxrdflib_graph.query(query)
        if into_store is None:
            store = Store()
            store_lock = None
        else:
            store = into_store
            store_lock = self.into_store_write_locks.get(id(into_store), None)
        if results.graph is None:
            return store
        if store_lock is not None:
            store_lock.acquire()
        try:
            default = DefaultGraph()
            store.bulk_extend(
                Quad(to_ox(t.subject), to_ox(t.predicate), to_ox(t.object), default)
                for t in results.graph.triples((None, None, None))
                )
        finally:
            if store_lock is not None:
                store_lock.release()
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
        if into_graph is not None:
            graph_lock = self.into_store_write_locks.get(id(into_graph), None)
            do_delete_lock = graph_lock is None
            if graph_lock is None:
                graph_lock = Lock()
                self.into_store_write_locks[id(into_graph)] = graph_lock
        else:
            graph_lock = None
            do_delete_lock = False
        try:
            return await run_in_threadpool(
                self._sync_rdf_query_to_rdflib_graph, query, into_graph
            )
        finally:
            if graph_lock is not None and do_delete_lock:
                # The Lock might still be acquired by a different thread, but doesn't matter,
                # we can still delete the lock reference from the dict.
                if id(into_graph) in self.into_store_write_locks and graph_lock is self.into_store_write_locks[id(into_graph)]:
                    del self.into_store_write_locks[id(into_graph)]

    async def rdf_query_to_oxigraph_store(
        self, query: str, into_store: Store | None = None
    ) -> Store:
        if into_store is not None:
            store_lock = self.into_store_write_locks.get(id(into_store), None)
            do_delete_lock = store_lock is None
            if store_lock is None:
                store_lock = Lock()
                self.into_store_write_locks[id(into_store)] = store_lock
        else:
            store_lock = None
            do_delete_lock = False
        try:
            return await run_in_threadpool(
                self._sync_rdf_query_to_oxigraph_store, query, into_store
            )
        finally:
            if store_lock is not None and do_delete_lock:
                # The Lock might still be acquired by a different thread, but doesn't matter,
                # we can still delete the lock reference from the dict.
                if id(into_store) in self.into_store_write_locks and store_lock is self.into_store_write_locks[id(into_store)]:
                    del self.into_store_write_locks[id(into_store)]
    async def tabular_query_to_table(
        self, query: str, context: URIRef | None = None
    ) -> tuple[URIRef | None, list[dict[str, Any]]]:
        return await run_in_threadpool(
            self._sync_tabular_query_to_table, query, context
        )

    def _str_type_for_rdflib_type(self, instance):
        map = {URIRef: "uri", BNode: "bnode", Literal: "literal"}
        return map[type(instance)]
