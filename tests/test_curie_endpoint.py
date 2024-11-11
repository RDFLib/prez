import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def setup(client):
    iri = "http://example.com/namespace/test"
    client.get(f"/identifier/curie/{iri}")


@pytest.mark.parametrize(
    "iri, expected_status_code",
    [
        ["d", 400],
        ["http://!", 400],
        ["http://example.com/namespace", 200],
    ],
)
def test_iri(iri: str, expected_status_code: int, client: TestClient):
    response = client.get(f"/identifier/curie/{iri}")
    assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "curie, expected_status_code",
    [
        ["d", 400],
        ["ns1", 400],
        ["namespace:test", 200],
    ],
)
def test_curie(curie: str, expected_status_code: int, client: TestClient, setup):
    response = client.get(f"/identifier/iri/{curie}")
    assert response.status_code == expected_status_code
