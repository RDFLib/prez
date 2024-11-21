import pytest
from fastapi.testclient import TestClient


def get_curie(client: TestClient, iri: str) -> str:
    response = client.get(f"/identifier/curie/{iri}")
    if response.status_code != 200:
        raise ValueError(f"Failed to retrieve curie for {iri}. {response.text}")
    return response.text


@pytest.mark.parametrize(
    "iri, inbound, outbound, count",
    [
        [
            "http://linked.data.gov.au/def/borehole-purpose",
            "http://www.w3.org/2004/02/skos/core#inScheme",
            None,
            0,
        ],
        [
            "http://linked.data.gov.au/def/borehole-purpose-no-children",
            "http://www.w3.org/2004/02/skos/core#inScheme",
            None,
            0,
        ],
        [
            "http://linked.data.gov.au/def/borehole-purpose",
            None,
            "http://www.w3.org/2004/02/skos/core#hasTopConcept",
            0,
        ],
    ],
)
def test_count(
    client: TestClient,
    iri: str,
    inbound: str | None,
    outbound: str | None,
    count: int,
):
    curie = get_curie(client, iri)
    params = {"curie": curie, "inbound": inbound, "outbound": outbound}
    response = client.get("/count", params=params)
    assert int(response.text) == count
