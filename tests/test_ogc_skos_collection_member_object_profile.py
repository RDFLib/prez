from fastapi.testclient import TestClient
from rdflib import Graph
from prez.reference_data.prez_ns import PREZ


def test_skos_collection_member_object_profile(client: TestClient):
    r = client.get("/object?uri=https://linked.data.gov.au/def/road-types/qld")
    response_graph = Graph().parse(data=r.text)
    assert (
        None,
        PREZ.currentProfile,
        PREZ.OGCSKOSCollectionObjectProfile,
    ) in response_graph
