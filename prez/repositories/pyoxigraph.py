import logging

import pyoxigraph
from fastapi.concurrency import run_in_threadpool
from rdflib import Namespace, Graph, URIRef

from prez.exceptions.model_exceptions import InvalidSPARQLQueryException
from prez.repositories.base import Repo

PREZ = Namespace("https://prez.dev/")

log = logging.getLogger(__name__)


class PyoxigraphRepo(Repo):
    def __init__(self, pyoxi_store: pyoxigraph.Store):
        self.pyoxi_store = pyoxi_store

    def _handle_query_solution_results(
        self, results: pyoxigraph.QuerySolutions
    ) -> dict:
        """Organise the query results into format serializable by FastAPIs JSONResponse."""
        variables = results.variables
        results_dict = {"head": {"vars": [v.value for v in results.variables]}}
        results_list = []
        for result in results:
            result_dict = {}
            for var in variables:
                binding = result[var]
                if binding:
                    binding_type = self._pyoxi_result_type(binding)
                    result_dict[str(var)[1:]] = {
                        "type": binding_type,
                        "value": binding.value,
                    }
            results_list.append(result_dict)
        results_dict["results"] = {"bindings": results_list}
        return results_dict

    @staticmethod
    def _handle_query_triples_results(results: pyoxigraph.QueryTriples) -> Graph:
        """Parse the query results into a Graph object."""
        ntriples = " .\n".join([str(r) for r in list(results)]) + " ."
        g = Graph()
        g.bind("prez", URIRef("https://prez.dev/"))
        if ntriples == " .":
            return g
        return g.parse(data=ntriples, format="ntriples")

    def _sync_rdf_query_to_graph(self, query: str) -> Graph:
        results = self.pyoxi_store.query(query)
        result_graph = self._handle_query_triples_results(results)
        return result_graph

    def _sync_tabular_query_to_table(self, query: str, context: URIRef = None) -> tuple:
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
        if isinstance(results, pyoxigraph.QuerySolutions):  # a SELECT query result
            results_dict = self._handle_query_solution_results(results)
            return results_dict
        elif isinstance(results, pyoxigraph.QueryTriples):  # a CONSTRUCT query result
            result_graph = self._handle_query_triples_results(results)
            return result_graph
        elif isinstance(results, bool):
            results_dict = {"head": {}, "boolean": results}
            return results_dict
        else:
            raise TypeError(f"Unexpected result class {type(results)}")

    async def rdf_query_to_graph(self, query: str) -> Graph:
        return await run_in_threadpool(self._sync_rdf_query_to_graph, query)

    async def tabular_query_to_table(self, query: str, context: URIRef = None) -> list:
        return await run_in_threadpool(
            self._sync_tabular_query_to_table, query, context
        )

    async def sparql(
        self, query: str, raw_headers: list[tuple[bytes, bytes]], method: str = ""
    ) -> list | Graph | bool:
        return self._sparql(query)

    @staticmethod
    def _pyoxi_result_type(term) -> str:
        if isinstance(term, pyoxigraph.Literal):
            return "literal"
        elif isinstance(term, pyoxigraph.NamedNode):
            return "uri"
        elif isinstance(term, pyoxigraph.BlankNode):
            return "bnode"
        else:
            raise ValueError(f"Unknown type: {type(term)}")
