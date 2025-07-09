import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Any
from pyoxigraph import Store
from rdflib import Graph, Namespace, URIRef

from prez.cache import prefix_graph

PREZ = Namespace("https://prez.dev/")

log = logging.getLogger(__name__)


class Repo(ABC):
    @abstractmethod
    async def rdf_query_to_rdflib_graph(
        self, query: str, into_graph: Graph | None = None
    ) -> Graph:
        pass

    @abstractmethod
    async def rdf_query_to_oxigraph_store(
        self, query: str, into_store: Store | None = None
    ) -> Store:
        pass

    @abstractmethod
    async def tabular_query_to_table(
        self, query: str, context: URIRef | None = None
    ) -> Tuple[URIRef | None, list[dict[str, Any]]]:
        pass

    async def send_queries(
        self,
        rdf_queries: List[str],
        tabular_queries: List[Tuple[URIRef | None, str]] = [],
        return_oxigraph_store: bool = False,
    ) -> Tuple[Graph | Store, List]:
        # Common logic to send both query types in parallel
        if return_oxigraph_store:
            s = Store()
            graph_queries = [
                self.rdf_query_to_oxigraph_store(query, into_store=s)
                for query in rdf_queries
                if query
            ]
            retstore = s
        else:
            g = Graph(namespace_manager=prefix_graph.namespace_manager)
            graph_queries = [
                self.rdf_query_to_rdflib_graph(query, into_graph=g)
                for query in rdf_queries
                if query
            ]
            retstore = g

        results = await asyncio.gather(
            *graph_queries,
            *[
                self.tabular_query_to_table(query, context)
                for context, query in tabular_queries
                if query
            ],
        )

        tabular_results = []
        for result in results:
            if isinstance(result, (Graph, Store)):
                pass
            else:
                tabular_results.append(result)
        return retstore, tabular_results

    @abstractmethod
    def sparql(
        self, query: str, raw_headers: list[tuple[bytes, bytes]], method: str = "GET"
    ):
        pass
