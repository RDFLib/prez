import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List
from typing import Tuple

from rdflib import Namespace, Graph, URIRef

PREZ = Namespace("https://prez.dev/")

log = logging.getLogger(__name__)


class Repo(ABC):
    @abstractmethod
    async def rdf_query_to_graph(self, query: str):
        pass

    @abstractmethod
    async def tabular_query_to_table(self, query: str, context: URIRef = None):
        pass

    async def send_queries(
        self,
        rdf_queries: List[str],
        tabular_queries: List[Tuple[URIRef | None, str]] = None,
    ) -> Tuple[Graph, List]:
        # Common logic to send both query types in parallel
        results = await asyncio.gather(
            *[self.rdf_query_to_graph(query) for query in rdf_queries if query],
            *[
                self.tabular_query_to_table(query, context)
                for context, query in tabular_queries
                if query
            ],
        )
        # from prez.cache import prefix_graph
        # g = Graph(namespace_manager=prefix_graph.namespace_manager)  #TODO find where else this can go. significantly degrades performance
        g = Graph()
        tabular_results = []
        for result in results:
            if isinstance(result, Graph):
                g += result
            else:
                tabular_results.append(result)
        return g, tabular_results

    @abstractmethod
    def sparql(
        self, query: str, raw_headers: list[tuple[bytes, bytes]], method: str = "GET"
    ):
        pass
