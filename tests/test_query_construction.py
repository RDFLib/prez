from rdflib import RDF, RDFS, URIRef
from rdflib.namespace import GEO

from prez.services.query_generation.classes import ClassesSelectQuery
from prez.services.query_generation.search import (
    SearchQueryRegex,
)
from prez.services.query_generation.umbrella import PrezQueryConstructor
from temp.grammar import *


def test_basic_object():
    PrezQueryConstructor(
        profile_triples=[
            SimplifiedTriple(
                subject=IRI(value="https://test-object"),
                predicate=IRI(value="https://prez.dev/ont/label"),
                object=Var(value="label"),
            ),
            SimplifiedTriple(
                subject=IRI(value="https://test-object"),
                predicate=IRI(value="https://property"),
                object=Var(value="propValue"),
            ),
        ],
    )


def test_basic_listing():
    test = PrezQueryConstructor(
        profile_triples=[
            SimplifiedTriple(
                subject=Var(value="focus_node"),
                predicate=IRI(value=str(RDF.type)),
                object=IRI(value=str(GEO.Feature)),
            ),
            SimplifiedTriple(
                subject=Var(value="focus_node"),
                predicate=IRI(value="https://property"),
                object=Var(value="propValue"),
            ),
        ],
        inner_select_triples=[
            SimplifiedTriple(
                subject=Var(value="focus_node"),
                predicate=IRI(value=str(RDF.type)),
                object=IRI(value=str(GEO.Feature)),
            ),
            SimplifiedTriple(
                subject=Var(value="focus_node"),
                predicate=IRI(value=str(RDFS.label)),
                object=Var(value="label"),
            ),
        ],
        limit=10,
        offset=0,
        order_by=Var(value="label"),
        order_by_direction="ASC",
    )
    print("")


def test_search_query_regex():
    sq = SearchQueryRegex(term="test", predicates=[RDFS.label])
    test = PrezQueryConstructor(
        profile_triples=[
            SimplifiedTriple(
                subject=Var(value="focus_node"),
                predicate=IRI(value=str(RDF.type)),
                object=IRI(value=str(GEO.Feature)),
            ),
            SimplifiedTriple(
                subject=Var(value="focus_node"),
                predicate=IRI(value="https://property"),
                object=Var(value="propValue"),
            ),
        ],
        additional_construct_triples=sq.construct_triples,
        inner_select_vars=sq.inner_select_vars,
        inner_select_gpnt=[sq.inner_select_gpnt],
        limit=sq.limit,
        offset=sq.offset,
        order_by=sq.order_by,
        order_by_direction=sq.order_by_direction,
    )


def test_classes():
    test = ClassesSelectQuery(
        uris=[IRI(value="https://test1"), IRI(value="https://test2")]
    )
    print(test.to_string())
