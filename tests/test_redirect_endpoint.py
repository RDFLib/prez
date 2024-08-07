import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "iri, url, expected_response_code, accept_header_value",
    [
        [
            "http://data.bgs.ac.uk/id/dataHolding/13603129",
            "http://metadata.bgs.ac.uk/geonetwork/srv/eng/catalog.search#/metadata/9df8df53-2a1d-37a8-e044-0003ba9b0d98",
            307,
            "",
        ],
        ["http://example.com/non-existent", None, 404, ""],
        [
            "http://data.bgs.ac.uk/id/dataHolding/13603129",
            "http://metadata.bgs.ac.uk/geonetwork/srv/eng/catalog.search#/metadata/9df8df53-2a1d-37a8-e044-0003ba9b0d98",
            307,
            "text/turtle",
        ],
    ],
)
def test_redirect_endpoint(
    client: TestClient,
    iri: str,
    url: str,
    expected_response_code,
    accept_header_value: str | None,
):
    params = {"iri": iri}
    headers = {"accept": accept_header_value}
    response = client.get(
        "/identifier/redirect", params=params, headers=headers, follow_redirects=False
    )

    if expected_response_code != 404:
        assert response.status_code == expected_response_code
        assert response.headers.get("location") == url

        if accept_header_value:
            assert response.headers.get("accept") == accept_header_value
    else:
        assert response.status_code == expected_response_code
        assert response.headers.get("content-type") == "application/json"
        data = response.json()
        assert data.get("status_code") == expected_response_code
        assert data.get("detail") == f"No homepage found for IRI {iri}."
