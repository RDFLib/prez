import pytest
from fastapi.testclient import TestClient

from prez.app import app


@pytest.fixture
def client() -> TestClient:
    testclient = TestClient(app)

    # Make a request for the following IRI to ensure
    # the curie is available in the 'test_curie' test.
    iri = "http://example.com/namespace/test"
    response = testclient.get(f"/identifier/curie/{iri}")
    assert response.status_code == 200
    assert response.text == "nmspc:test"

    return testclient


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
        ["nmspc:test", 200],
    ],
)
def test_curie(curie: str, expected_status_code: int, client: TestClient):
    response = client.get(f"/identifier/iri/{curie}")
    assert response.status_code == expected_status_code
