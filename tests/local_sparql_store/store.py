import urllib.parse
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import argparse
from rdflib import Graph


class SparqlServer(BaseHTTPRequestHandler):
    """A small SPARQL Protocol server for Prez testing.

    This small HTTP server makes two endpoints available:

        * http://{host}:{port}/vocprez
        * http://{host}:{port}/spaceprez

    It will only accept GET requests to these two endpoints with a 'query' query string parameter, e.g.

        http://localhost:3030/vocprez?query=...

    It expects a quote plus-encoded SPARQL query, e.g.:

        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT (COUNT(?cs) AS ?count)
        WHERE {
          ?cs a skos:ConceptScheme
        }

    -->

        http://localhost:3030/vocprez?query=PREFIX+skos%3A+%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2Fskos%2Fcore%23%3E%0A%0ASELECT+%28COUNT%28%3Fcs%29+AS+%3Fcount%29+%0AWHERE+%7B+%0A++%3Fcs+a+skos%3AConceptScheme+%0A%7D

    It returns responses using separate VocPrez and SpacePrez graphs which are the contents of the vocprez_... &
    spaceprez_... files in the dummy_data/ folder.

    TO RUN:

        python store.py

    Then the VocPrez SPARQL endpoint would be http://localhost:3030/vocprez
    """

    def __init__(self, *args):
        self.vocprez_graph = self.load_vocprez_graph()
        self.spaceprez_graph = self.load_spaceprez_graph()

        BaseHTTPRequestHandler.__init__(self, *args)

    @lru_cache
    def load_vocprez_graph(self):
        g = Graph()
        for f in Path(Path(__file__).parent / "data" / "vocprez").glob("*.ttl"):
            g.parse(f)
        return g

    @lru_cache
    def load_spaceprez_graph(self):
        g = Graph()
        for f in Path(Path(__file__).parent / "data" / "spaceprez").glob("*.ttl"):
            g.parse(f)
        return g

    def do_GET(self):
        status, content_type, content = self.validate_path()

        if status is not None:
            return self.http_response(status, content_type, content)

        if self.path == "/vocprez":
            status = 200
            content_type = "text/plain"
            content = "Local VocPrez SPARQL store"
        if self.path == "/spaceprez":
            status = 200
            content_type = "text/plain"
            content = "Local SpacPrez SPARQL store"

        if status is not None:
            return self.http_response(status, content_type, content)

        if "query=" not in self.path:
            return self.http_response(
                400,
                "text/plain",
                "You are missing a query in your GET request (query=...)",
            )

        # get query from URL query string args
        # only handle encoded queries
        query = urllib.parse.unquote_plus(self.path.split("query=")[1])

        self.apply_sparql_query(query)

    def do_POST(self):
        status, content_type, content = self.validate_path()

        if status is not None:
            return self.http_response(status, content_type, content)

        # get query from POST body
        query = self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8")

        self.apply_sparql_query(query)

    def do_HEAD(self):
        return self.http_response(200, "text/plain", "")

    def validate_path(self):
        status = None
        content_type = None
        content = None

        if self.path == "/":
            status = 200
            content_type = "text/plain"
            content = "Local SPARQL store"
        elif not self.path.startswith(("/vocprez", "/spaceprez")):
            status = 404
            content_type = "text/plain"
            content = "Endpoint unknown"

        return status, content_type, content

    def apply_sparql_query(self, query):
        print(f"query: {query}")
        try:
            if "vocprez" in self.path:
                result = self.vocprez_graph.query(query)
            else:  # "spaceprez" in self.path:
                result = self.spaceprez_graph.query(query)

            if "CONSTRUCT" in query or "DESCRIBE" in query:
                content_type = "text/turtle"
            else:
                content_type = "application/sparql-results+json"

            return self.http_response(
                200, content_type, result.serialize(format=content_type).decode()
            )
        except Exception as e:
            return self.http_response(
                400, "text.plain", f"Your SPARQL query could not be interpreted: {e}"
            )

    def http_response(self, status, content_type, content):
        self.send_response(status)
        self.send_header("Content-type", content_type)
        self.end_headers()
        self.wfile.write(bytes(f"{content}\n", "utf-8"))
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-p", "--port", default=3030, help="Optionally a port to run on"
    )
    args = parser.parse_args()

    srv = HTTPServer(("localhost", int(args.port)), SparqlServer)
    print(f"Local SPARQL server started on port {args.port}")
    srv.serve_forever()
