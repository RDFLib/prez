"""Benchmark Prez SPARQL query construction and the request path around it.

Run from the repository root::

    poetry run python benchmark/query_construction.py --label before
    poetry run python benchmark/query_construction.py --label after
    poetry run python benchmark/compare.py benchmark/results/before.json benchmark/results/after.json

Only Prez's own entry points are used (query classes, ``NodeShape``, ``CQLParser``,
``PrezQueryConstructor``, the FastAPI app), so the script runs unchanged against the
``sparql-grammar-pydantic`` and ``sparql-grammar`` based code and the numbers are
directly comparable.

Scenarios, in the order the request path meets them:

* ``annotations`` / ``classes`` / ``link_generation`` - the queries that get a large
  ``VALUES`` clause substituted in (one IRI per term / focus node). These scale with
  the size of the response being annotated, so they are run at several sizes.
* ``listing`` - a listing request's pre-query work: SHACL node shapes for the endpoint
  and the profile, the CONSTRUCT query, and the count query (which deep-copies the
  inner select).
* ``cql_in`` - a CQL ``in`` filter with many values.
* ``search`` - the default regex search query.
* ``e2e_*`` - whole requests through the FastAPI app against an in-memory pyoxigraph
  store loaded with ``test_data``. ``cold`` clears the link and class caches before
  every request; ``warm`` reuses them. There is no network hop, so these are the
  CPU cost of a request end to end.

Timings are the minimum and median over ``--repeat`` runs of ``time.perf_counter``.
Node counts are the size of the grammar tree built, which is deterministic and so
comparable across machines - see ``benchmark/README.md`` for how it is used.

``--dump-queries DIR`` writes every rendered query to ``DIR`` so two versions of the
code can be checked for producing equivalent SPARQL.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import gc
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("SPARQL_REPO_TYPE", "pyoxigraph_memory")
os.environ.setdefault("ENABLE_SPARQL_ENDPOINT", "true")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from rdflib import Graph, URIRef  # noqa: E402
from rdflib.namespace import RDF, SKOS  # noqa: E402

EX = "http://example.org/"

#: Sizes for the scenarios that scale with the size of the response: a VALUES row or
#: a triple pattern per term. The large end is not hypothetical - a client listing
#: 100,000 concepts substitutes 100,000 IRIs into the annotations, class lookup and
#: link generation queries. Override with ``--sizes`` for a quick run.
SIZES = (100, 1_000, 5_000, 10_000, 50_000, 100_000)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def timed(fn, repeat: int) -> tuple[list[float], object]:
    """Run ``fn`` ``repeat`` times; return the durations in ms and the last result."""
    durations = []
    result = None
    for _ in range(repeat):
        gc.collect()
        start = time.perf_counter()
        result = fn()
        durations.append((time.perf_counter() - start) * 1000)
    return durations, result


def stats(durations: list[float]) -> dict:
    return {
        "min_ms": round(min(durations), 3),
        "median_ms": round(statistics.median(durations), 3),
    }


def count_nodes(node) -> int:
    """Size of a grammar tree, for either library."""
    if hasattr(node, "walk"):  # sparql-grammar
        return sum(1 for _ in node.walk())
    seen = 0  # sparql-grammar-pydantic
    stack = [node]
    while stack:
        current = stack.pop()
        if hasattr(current, "model_fields"):
            seen += 1
            for name in type(current).model_fields:
                value = getattr(current, name, None)
                if isinstance(value, (list, tuple)):
                    stack.extend(value)
                elif value is not None:
                    stack.append(value)
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return seen


class Recorder:
    """Collects scenario results and, optionally, the rendered queries."""

    def __init__(self, repeat: int, dump_dir: Path | None):
        self.repeat = repeat
        self.dump_dir = dump_dir
        self.results: dict[str, dict] = {}
        if dump_dir:
            dump_dir.mkdir(parents=True, exist_ok=True)

    def scenario(self, name: str, build, render=None, n: int | None = None, extra=None):
        """Time ``build()`` and ``render(built)`` separately, record node/char counts.

        A scenario that raises is recorded as a failure and the run carries on: at
        the large sizes that is itself the result worth having, since the previous
        library hit a recursion limit past a certain query size.
        """
        entry: dict = {"n": n}
        try:
            build_times, built = timed(build, self.repeat)
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["total"] = {"min_ms": None, "median_ms": None}
            self.results[name] = entry
            print(f"{name:32s} {json.dumps(entry)}", flush=True)
            return None
        entry["build"] = stats(build_times)
        if render is not None:
            try:
                render_times, text = timed(lambda: render(built), self.repeat)
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
                entry["total"] = {"min_ms": None, "median_ms": None}
                self.results[name] = entry
                print(f"{name:32s} {json.dumps(entry)}", flush=True)
                return built
            entry["render"] = stats(render_times)
            entry["total"] = {
                "min_ms": round(min(build_times) + min(render_times), 3),
                "median_ms": round(
                    statistics.median(build_times) + statistics.median(render_times), 3
                ),
            }
            entry["chars"] = len(text)
            self._dump(name, text)
        else:
            entry["total"] = entry["build"]
        if hasattr(built, "to_string") or hasattr(built, "model_fields"):
            entry["nodes"] = count_nodes(built)
        if extra:
            entry.update(extra)
        self.results[name] = entry
        print(f"{name:32s} {json.dumps(entry)}", flush=True)
        return built

    def _dump(self, name: str, text: str) -> None:
        if self.dump_dir:
            (self.dump_dir / f"{name}.rq").write_text(text)


def load_graph(path: Path) -> Graph:
    graph = Graph()
    for file in sorted(path.rglob("*.ttl")):
        graph.parse(file)
    return graph


# ---------------------------------------------------------------------------
# construction scenarios
# ---------------------------------------------------------------------------


def bench_values_queries(rec: Recorder) -> None:
    from prez.services.query_generation.annotations import AnnotationsConstructQuery
    from prez.services.query_generation.classes import ClassesSelectQuery

    for n in SIZES:
        iris = [f"https://example.com/term/{i}" for i in range(n)]
        rec.scenario(
            f"annotations_values_{n}",
            lambda: AnnotationsConstructQuery(terms=_iris(iris)),
            lambda q: q.to_string(),
            n=n,
        )
        rec.scenario(
            f"classes_values_{n}",
            lambda: ClassesSelectQuery(iris=_iris(iris)),
            lambda q: q.to_string(),
            n=n,
        )


def _iris(values):
    from prez.services.query_generation import shacl  # noqa: F401 - import side effects

    IRI = _grammar().IRI
    return [IRI(value=v) for v in values]


def _grammar():
    try:
        import sparql_grammar as grammar  # new
    except ImportError:  # pragma: no cover - old code
        import sparql_grammar_pydantic as grammar
    return grammar


class RecordingRepo:
    """A Repo that records the queries it is asked to send and returns no rows."""

    def __init__(self):
        self.queries: list[str] = []

    async def send_queries(
        self, rdf_queries, tabular_queries=(), return_oxigraph_store=False
    ):
        self.queries.extend(rdf_queries)
        results = []
        for uri, query in tabular_queries:
            self.queries.append(query)
            results.append((uri, []))
        return None, results


def bench_link_generation(rec: Recorder, endpoints_graph: Graph) -> None:
    from pyoxigraph import NamedNode

    from prez.services.link_generation import get_link_components_many
    from prez.services.query_generation.shacl import NodeShape

    Var = _grammar().Var
    shape_uri = URIRef(EX + "shape-R0-HL3")
    for n in SIZES:
        nodes = [NamedNode(f"https://example.com/concept/{i}") for i in range(n)]

        def build():
            # exactly what _link_generation_many does per class: build the shape,
            # then the VALUES-driven select for every uncached focus node
            ns = NodeShape(
                uri=shape_uri,
                graph=endpoints_graph,
                kind="endpoint",
                focus_node=Var(value="_link_focus_node"),
            )
            repo = RecordingRepo()
            asyncio.run(get_link_components_many(ns, nodes, repo))
            return repo.queries[0]

        name = f"link_generation_values_{n}"
        query = rec.scenario(name, build, n=n)
        if query is not None:
            rec.results[name]["chars"] = len(query)
            rec._dump(name, query)


def bench_lucene_search(rec: Recorder) -> None:
    """Build the Jena Lucene search query, with and without facets.

    The largest single query builder in prez, and the one a GSWA request goes
    through, so it is measured on its own rather than only inside a listing.
    """
    from prez.services.query_generation.search_jena_lucene import SearchQueryJenaLucene
    from prez.services.query_generation.umbrella import PrezQueryConstructor

    def _consumed(query):
        """Touch what a listing request consumes: the class builds its parts lazily."""
        query.inner_select_gpnt
        query.tss_list
        query.inner_select_vars
        return query

    def plain():
        return _consumed(
            SearchQueryJenaLucene(
                term="ore", limit=20, offset=0, lucene_index_name="default"
            )
        )

    def with_facets_and_filter():
        return _consumed(
            SearchQueryJenaLucene(
                term="ore",
                limit=20,
                offset=0,
                lucene_index_name="default",
                facets=["type", "status"],
                filter_json={"op": "=", "args": [{"property": "status"}, "active"]},
                order_by="label",
                order_by_direction="ASC",
            )
        )

    for name, build in (
        ("lucene_search", plain),
        ("lucene_search_facets", with_facets_and_filter),
    ):
        query = rec.scenario(name, build)
        if query is None:
            continue
        # the parts a listing query actually consumes
        rendered = query.inner_select_gpnt.to_string()
        rec.results[name]["chars"] = len(rendered)
        rec.results[name]["nodes"] = count_nodes(query.inner_select_gpnt)
        rec._dump(name, rendered)

    search = plain()

    def whole_listing():
        return PrezQueryConstructor(
            construct_tss_list=list(search.tss_list),
            inner_select_vars=list(search.inner_select_vars),
            inner_select_gpnt=[search.inner_select_gpnt],
            limit=search.limit,
            offset=search.offset,
            order_by_value=search.order_by_val,
            order_by_direction=search.order_by_direction,
        )

    rec.scenario("lucene_listing_query", whole_listing, lambda q: q.to_string())


def bench_materialisation(rec: Recorder) -> None:
    """Move the results of a CONSTRUCT into a store, through the repository.

    Every RDF response goes through here, and the cost scales with the size of the
    response rather than the size of the query, so a listing of 100,000 concepts
    pays it 100,000 times over.
    """
    from pyoxigraph import RdfFormat

    from prez.cache import store as data_store
    from prez.repositories import PyoxigraphRepo

    for file in (REPO_ROOT / "test_data").glob("**/*.ttl"):
        data_store.load(file.read_bytes(), RdfFormat.TURTLE)
    repo = PyoxigraphRepo(data_store)
    query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"

    def into_new_store():
        return asyncio.run(repo.rdf_query_to_oxigraph_store(query))

    result = rec.scenario("materialise_construct", into_new_store, n=len(data_store))
    if result is not None:
        rec.results["materialise_construct"]["triples"] = len(result)


def bench_link_generation_end_to_end(rec: Recorder) -> None:
    """Generate links for a store of objects, the way a response does.

    Covers everything issue #474 names: the class lookup, the node shapes, the
    components query per class, and the link and identifier strings per solution.
    Run cold (nothing cached) and warm (every link already in the cache), because a
    deployment serving a listing repeatedly is in the warm case.
    """
    from pyoxigraph import NamedNode, Quad, RdfFormat, Store

    from prez.cache import links_ids_graph_cache, store as data_store
    from prez.repositories import PyoxigraphRepo
    from prez.services.link_generation import add_prez_links_for_oxigraph

    for file in (REPO_ROOT / "test_data").glob("**/*.ttl"):
        data_store.load(file.read_bytes(), RdfFormat.TURTLE)
    repo = PyoxigraphRepo(data_store)
    concept = NamedNode("http://www.w3.org/2004/02/skos/core#Concept")
    rdf_type = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    uris = sorted(
        {q.subject.value for q in data_store.quads_for_pattern(None, rdf_type, concept)}
    )
    if not uris:
        print("link_generation_e2e: no concepts in test_data, skipped", flush=True)
        return
    nodes = [NamedNode(u) for u in uris]
    structure = ("catalogs", "collections", "items")

    def run():
        target = Store()
        target.bulk_extend(
            Quad(n, rdf_type, concept, n) for n in nodes  # something to attach links to
        )
        asyncio.run(add_prez_links_for_oxigraph(target, repo, structure, uris=nodes))
        return target

    def cold():
        links_ids_graph_cache.clear()
        asyncio.run(_clear_class_cache())
        return run()

    rec.scenario("link_generation_e2e_cold", cold, n=len(nodes))
    rec.scenario("link_generation_e2e_warm", run, n=len(nodes))


async def _clear_class_cache():
    from aiocache import caches

    await caches.get("classes").clear()


def bench_listing(rec: Recorder, endpoints_graph: Graph, profiles_graph: Graph) -> None:
    from prez.models.query_params import ListingQueryParams
    from prez.services.query_generation.count import CountQuery
    from prez.services.query_generation.shacl import NodeShape
    from prez.services.query_generation.umbrella import (
        PrezQueryConstructor,
        merge_listing_query_grammar_inputs,
    )

    g = _grammar()
    Var, IRI = g.Var, g.IRI
    endpoint_shape = URIRef(EX + "shape-R0-HL3")
    profile_uri = URIRef("https://prez.dev/OGCListingProfile")
    parent = "https://example.com/vocab/scheme-1"
    catalog = "https://example.com/catalog-1"
    qp = ListingQueryParams(
        limit=20,
        page=1,
        _filter=None,
        bbox=[],
        datetime=None,
        order_by=None,
        order_by_direction=None,
    )

    def shapes():
        endpoint_ns = NodeShape(
            uri=endpoint_shape,
            graph=endpoints_graph,
            kind="endpoint",
            focus_node=Var(value="focus_node"),
            path_nodes={
                "path_node_1": IRI(value=parent),
                "path_node_2": IRI(value=catalog),
            },
        )
        profile_ns = NodeShape(
            uri=profile_uri,
            graph=profiles_graph,
            kind="profile",
            focus_node=Var(value="focus_node"),
        )
        return endpoint_ns, profile_ns

    endpoint_ns, profile_ns = rec.scenario("listing_nodeshapes", shapes)

    def build_query():
        kwargs = merge_listing_query_grammar_inputs(
            endpoint_nodeshape=endpoint_ns, query_params=qp
        )
        construct_tss_list = kwargs.pop("construct_tss_list") + list(
            profile_ns.tss_list
        )
        return PrezQueryConstructor(
            construct_tss_list=construct_tss_list,
            profile_triples=profile_ns.tssp_list,
            profile_gpnt=profile_ns.gpnt_list,
            **kwargs,
        )

    main_query = rec.scenario("listing_query", build_query, lambda q: q.to_string())
    rec.scenario(
        "listing_count_query",
        lambda: CountQuery(original_subselect=copy.deepcopy(main_query.inner_select)),
        lambda q: q.to_string(),
    )
    rec.scenario(
        "listing_deepcopy_inner_select", lambda: copy.deepcopy(main_query.inner_select)
    )

    def object_query():
        ns = NodeShape(
            uri=profile_uri,
            graph=profiles_graph,
            kind="profile",
            focus_node=IRI(value=parent),
        )
        return PrezQueryConstructor(
            construct_tss_list=list(ns.tss_list),
            profile_triples=ns.tssp_list,
            profile_gpnt=ns.gpnt_list,
        )

    rec.scenario("object_query", object_query, lambda q: q.to_string())


def bench_cql_and_search(rec: Recorder) -> None:
    from prez.services.query_generation.cql import CQLParser
    from prez.services.query_generation.search_default import SearchQueryRegex
    from prez.services.query_generation.umbrella import PrezQueryConstructor

    for n in SIZES:
        cql = {
            "op": "and",
            "args": [
                {
                    "op": "in",
                    "args": [
                        {"property": "https://example.com/p"},
                        [f"https://example.com/v/{i}" for i in range(n)],
                    ],
                },
                {"op": "=", "args": [{"property": "https://example.com/q"}, "x"]},
            ],
        }

        def build():
            parser = CQLParser(cql_json=cql)
            parser.parse()
            return parser

        parser = rec.scenario(f"cql_in_{n}", build, n=n)
        if parser is not None:
            rec.results[f"cql_in_{n}"]["chars"] = len(parser.query_str)
            rec.results[f"cql_in_{n}"]["nodes"] = count_nodes(parser.query_object)
            rec._dump(f"cql_in_{n}", parser.query_str)

    def search():
        sq = SearchQueryRegex(term="test", limit=10, offset=0)
        return PrezQueryConstructor(
            construct_tss_list=sq.tss_list,
            inner_select_vars=sq.inner_select_vars,
            inner_select_gpnt=[sq.inner_select_gpnt],
            limit=sq.limit,
            offset=sq.offset,
            order_by_value=sq.order_by_val,
            order_by_direction=sq.order_by_direction,
        )

    rec.scenario("search_query", search, lambda q: q.to_string())


# ---------------------------------------------------------------------------
# end to end
# ---------------------------------------------------------------------------


def make_client():
    """The app, wired to an in-memory store holding ``test_data``.

    The data is loaded into the store the app builds its own repository around,
    rather than through ``dependency_overrides``: an override makes FastAPI rebuild
    the dependant tree for every sub-dependency on every request, which is signature
    inspection no deployment ever pays for and would swamp these numbers.
    """
    from fastapi.testclient import TestClient
    from pyoxigraph import RdfFormat

    from prez.app import assemble_app
    from prez.cache import store

    for file in (REPO_ROOT / "test_data").glob("**/*.ttl"):
        store.load(file.read_bytes(), RdfFormat.TURTLE)
    client = TestClient(assemble_app())
    client.__enter__()
    return client


def reset_request_caches() -> None:
    """Forget generated links and class lookups, so the next request redoes them."""
    from aiocache import caches

    from prez.cache import links_ids_graph_cache

    links_ids_graph_cache.clear()
    asyncio.run(caches.get("classes").clear())
    asyncio.run(caches.get("default").clear())


def discover_urls(client) -> dict[str, str]:
    """Follow prez:link values in responses to find real listing and object URLs."""
    PREZ_LINK = URIRef("https://prez.dev/link")
    DCAT_CATALOG = URIRef("http://www.w3.org/ns/dcat#Catalog")
    headers = {
        "Accept": "text/anot+turtle"
    }  # links are only added for annotated mediatypes
    urls = {"catalogs": "/catalogs?limit=20"}
    g = Graph().parse(data=client.get("/catalogs?limit=20", headers=headers).text)
    catalog = g.value(URIRef("https://example.com/CatalogOne"), PREZ_LINK)
    if catalog is not None:
        urls["catalog_object"] = str(catalog)
        urls["collections"] = f"{catalog}/collections?limit=20"
    # a concept listing is the heaviest common page: every concept needs a link
    # generated through the scheme and catalog, and every term needs annotating
    # sorted so that two runs pick the same scheme and stay comparable
    for catalog in sorted(g.subjects(RDF.type, DCAT_CATALOG)):
        link = g.value(catalog, PREZ_LINK)
        if link is None:
            continue
        cg = Graph().parse(
            data=client.get(f"{link}/collections?limit=20", headers=headers).text
        )
        for scheme in sorted(cg.subjects(RDF.type, SKOS.ConceptScheme)):
            scheme_link = cg.value(scheme, PREZ_LINK)
            if scheme_link is not None:
                urls["concepts"] = f"{scheme_link}/items?limit=100"
                urls["concept_scheme_object"] = str(scheme_link)
                break
        if "concepts" in urls:
            break
    urls["search"] = "/search?q=the&limit=20"
    return urls


def bench_e2e(rec: Recorder) -> None:
    client = make_client()
    try:
        urls = discover_urls(client)
        print("e2e urls:", json.dumps(urls, indent=1), flush=True)
        for key, url in urls.items():
            headers = {"Accept": "text/anot+turtle"}

            def cold():
                reset_request_caches()
                r = client.get(url, headers=headers)
                assert r.status_code == 200, (url, r.status_code, r.text[:200])
                return r

            def warm():
                r = client.get(url, headers=headers)
                assert r.status_code == 200, (url, r.status_code, r.text[:200])
                return r

            response = rec.scenario(f"e2e_cold_{key}", cold, extra={"url": url})
            rec.scenario(f"e2e_warm_{key}", warm, extra={"url": url})
            rec.results[f"e2e_cold_{key}"]["response_bytes"] = len(response.content)
    finally:
        client.__exit__(None, None, None)


# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--label", default="run", help="name of the results file")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--dump-queries", type=Path, default=None)
    parser.add_argument("--skip-e2e", action="store_true")
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="*",
        default=None,
        metavar="N",
        help=f"sizes for the scaling scenarios (default: {' '.join(str(s) for s in SIZES)})",
    )
    parser.add_argument(
        "--only", nargs="*", default=None, help="subset of: values link listing cql e2e"
    )
    args = parser.parse_args()

    if args.sizes:
        globals()["SIZES"] = tuple(args.sizes)

    rec = Recorder(args.repeat, args.dump_queries)
    endpoints_graph = load_graph(
        REPO_ROOT / "prez/reference_data/endpoints/data_endpoints_default"
    )
    profiles_graph = load_graph(REPO_ROOT / "prez/reference_data/profiles")

    groups = {
        "values": lambda: bench_values_queries(rec),
        "link": lambda: bench_link_generation(rec, endpoints_graph),
        "linke2e": lambda: bench_link_generation_end_to_end(rec),
        "lucene": lambda: bench_lucene_search(rec),
        "materialise": lambda: bench_materialisation(rec),
        "listing": lambda: bench_listing(rec, endpoints_graph, profiles_graph),
        "cql": lambda: bench_cql_and_search(rec),
        "e2e": lambda: bench_e2e(rec),
    }
    selected = args.only or list(groups)
    if args.skip_e2e and "e2e" in selected:
        selected.remove("e2e")
    for name in selected:
        groups[name]()

    grammar = _grammar()
    out = {
        "label": args.label,
        "python": platform.python_version(),
        "grammar_library": getattr(grammar, "__name__", "?"),
        "grammar_version": getattr(grammar, "__version__", "?"),
        "repeat": args.repeat,
        "sizes": list(SIZES),
        "results": rec.results,
    }
    out_path = REPO_ROOT / "benchmark/results" / f"{args.label}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
