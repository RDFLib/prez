import logging
from threading import Lock
from typing import Any

import pyoxigraph
from fastapi.concurrency import run_in_threadpool
from pyoxigraph import (
    RdfFormat,
    Store,
    QueryTriples,
    QuerySolutions,
    QueryBoolean,
    Quad,
)
from rdflib import Graph, Namespace, URIRef

from prez.exceptions.model_exceptions import InvalidSPARQLQueryException
from prez.repositories.base import Repo

PREZ = Namespace("https://prez.dev/")

log = logging.getLogger(__name__)


class PyoxigraphRepo(Repo):
    def __init__(self, pyoxi_store: Store):
        self.pyoxi_store = pyoxi_store
        self.into_store_write_locks = {}

    @staticmethod
    def _handle_query_solution_results(results: QuerySolutions) -> dict[str, Any]:
        """Organise the query results into format serializable by FastAPIs JSONResponse.

        A solution iterates its bindings in the order of ``results.variables``, and an
        unbound variable yields None, so the names are paired with the values by
        position rather than looked up per row. Link generation and class lookups run
        this over every result of every request, so the per-binding work is kept to
        the dict literal and one type test.
        """
        names = [v.value for v in results.variables]
        results_list: list[dict] = []
        for result in results:
            result_dict = {}
            for name, binding in zip(names, result):
                if binding is not None:
                    result_dict[name] = {
                        "type": _pyoxi_result_type(binding),
                        "value": binding.value,
                    }
            results_list.append(result_dict)
        return {"head": {"vars": names}, "results": {"bindings": results_list}}

    @staticmethod
    def _handle_query_triples_results(
        results: QueryTriples, into_: Graph | Store
    ) -> Graph | Store:
        """Parse the query results into a rdflib.Graph or pyoxigraph.Store."""
        if isinstance(into_, Store):
            # Into an oxigraph store
            default = pyoxigraph.DefaultGraph()
            # If the target is a Store, we can directly load the triples into it.
            into_.bulk_extend(
                Quad(t.subject, t.predicate, t.object, default) for t in results
            )
            return into_
        ntriples_bytes = results.serialize(None, format=RdfFormat.N_TRIPLES)
        if ntriples_bytes is None:
            # If the results are empty, return the empty store or graph.
            return into_
        if len(ntriples_bytes) < 3:
            return into_
        return into_.parse(data=ntriples_bytes, format="ntriples")

    def _sync_rdf_query_to_rdflib_graph(
        self, query: str, into_graph: Graph | None
    ) -> Graph:
        results = self.pyoxi_store.query(query)
        if into_graph is not None:
            g = into_graph
            graph_lock = self.into_store_write_locks.get(id(into_graph), None)
            if graph_lock is not None:
                graph_lock.acquire()
        else:
            g = Graph()
            g.bind("prez", URIRef("https://prez.dev/"))
            graph_lock = None
        try:
            result_graph = self._handle_query_triples_results(results, into_=g)
        finally:
            if graph_lock is not None:
                graph_lock.release()
        return result_graph

    def _sync_rdf_query_to_oxigraph_store(
        self, query: str, into_store: Store | None
    ) -> Store:
        results = self.pyoxi_store.query(query)
        if into_store is not None:
            s = into_store
            store_lock = self.into_store_write_locks.get(id(into_store), None)
            if store_lock is not None:
                store_lock.acquire()
        else:
            s = Store()
            store_lock = None
        try:
            result_store = self._handle_query_triples_results(results, into_=s)
        finally:
            if store_lock is not None:
                store_lock.release()
        return result_store

    def _sync_tabular_query_to_table(
        self, query: str, context: URIRef | None = None
    ) -> tuple[URIRef | None, list[dict]]:
        results = self.pyoxi_store.query(query)
        results_dict = self._handle_query_solution_results(results)
        # only return the bindings from the results.
        return context, results_dict["results"]["bindings"]

    def _sparql(self, query: str) -> dict | Graph | bool:
        """Submit a sparql query to the pyoxigraph store and return the formatted results."""
        try:
            results = self.pyoxi_store.query(query)
        except SyntaxError as e:
            raise InvalidSPARQLQueryException(e.msg)
        if isinstance(results, QuerySolutions):  # a SELECT query result
            results_dict = self._handle_query_solution_results(results)
            return results_dict
        elif isinstance(results, QueryTriples):  # a CONSTRUCT query result
            # TODO: should this be selectable between rdflib.Graph and pyoxigraph.Store?
            to_graph = Graph()
            to_graph.bind("prez", URIRef("https://prez.dev/"))
            result_graph = self._handle_query_triples_results(results, to_graph)
            return result_graph
        elif isinstance(results, QueryBoolean):
            results_dict = {"head": {}, "boolean": bool(results)}
            return results_dict
        else:
            raise TypeError(f"Unexpected result class {type(results)}")

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
                if (
                    id(into_graph) in self.into_store_write_locks
                    and graph_lock is self.into_store_write_locks[id(into_graph)]
                ):
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
                if (
                    id(into_store) in self.into_store_write_locks
                    and store_lock is self.into_store_write_locks[id(into_store)]
                ):
                    del self.into_store_write_locks[id(into_store)]

    async def tabular_query_to_table(
        self, query: str, context: URIRef | None = None
    ) -> tuple[URIRef | None, list[dict[str, Any]]]:
        return await run_in_threadpool(
            self._sync_tabular_query_to_table, query, context
        )

    async def sparql(
        self, query: str, raw_headers: list[tuple[bytes, bytes]], method: str = ""
    ) -> list | Graph | bool:
        return self._sparql(query)


#: pyoxigraph term class -> its name in the SPARQL results JSON format. A dict lookup
#: on the exact class, since these are final types with no subclasses.
_RESULT_TYPES = {
    pyoxigraph.Literal: "literal",
    pyoxigraph.NamedNode: "uri",
    pyoxigraph.BlankNode: "bnode",
}


def _pyoxi_result_type(term) -> str:
    try:
        return _RESULT_TYPES[type(term)]
    except KeyError:
        raise ValueError(f"Unknown type: {type(term)}") from None
