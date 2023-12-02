from rdflib import Graph, URIRef, SKOS, Literal, XSD
from rdflib.namespace import RDF, DCAT

from prez.reference_data.prez_ns import PREZ


def test_concept_hierarchy_top_concepts(client):
    r = client.get(
        f"/concept-hierarchy/exm:SchemingConceptScheme/top-concepts?_mediatype=text/turtle"
    )
    response_graph = Graph().parse(data=r.text)
    expected_response_1 = (
        URIRef("https://example.com/TopLevelConcept"),
        RDF.type,
        SKOS.Concept,
    )
    expected_response_2 = (
        URIRef("https://example.com/TopLevelConcept"),
        PREZ.hasChildren,
        Literal("true", datatype=XSD.boolean),
    )
    assert next(response_graph.triples(expected_response_1))
    assert next(response_graph.triples(expected_response_2))


def test_concept_hierarchy_narrowers(client):
    r = client.get(
        f"/concept-hierarchy/exm:TopLevelConcept/narrowers?_mediatype=text/turtle"
    )
    response_graph = Graph().parse(data=r.text)
    expected_response_1 = (
        URIRef("https://example.com/SecondLevelConcept"),
        RDF.type,
        SKOS.Concept,
    )
    expected_response_2 = (
        URIRef("https://example.com/SecondLevelConcept"),
        PREZ.hasChildren,
        Literal("true", datatype=XSD.boolean),
    )
    assert next(response_graph.triples(expected_response_1))
    assert next(response_graph.triples(expected_response_2))
