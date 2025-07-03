from fastapi.testclient import TestClient
from rdflib import Graph, URIRef, SKOS
from prez.reference_data.prez_ns import PREZ


def test_skos_collection_member_object_profile(client: TestClient):
    r = client.get("/object?uri=https://linked.data.gov.au/def/road-types/qld")
    response_graph = Graph().parse(data=r.text)
    assert (
        None,
        PREZ.currentProfile,
        PREZ.OGCSKOSCollectionObjectProfile,
    ) in response_graph


def test_skos_concept_scheme_object_profile_returns_incoming_in_scheme_from_skos_collection(
    client: TestClient,
):
    r = client.get("/object?uri=https://linked.data.gov.au/def/road-types")
    response_graph = Graph().parse(data=r.text)

    # /qld is a skos:Collection, it should exist in the response.
    assert (
        URIRef("https://linked.data.gov.au/def/road-types/qld"),
        SKOS.inScheme,
        URIRef("https://linked.data.gov.au/def/road-types"),
    ) in response_graph

    # /yard is a skos:Concept, it should not exist in the response.
    assert (
        URIRef("https://linked.data.gov.au/def/road-types/yard"),
        SKOS.inScheme,
        URIRef("https://linked.data.gov.au/def/road-types"),
    ) not in response_graph
