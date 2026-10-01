from fastapi.testclient import TestClient


def test_docs_openapi_schema_is_available(client: TestClient):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["openapi"].startswith("3.")
