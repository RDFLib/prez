from fastapi.testclient import TestClient


def test_search_empty_term_no_filters(client: TestClient):
    """Test that empty search term without filters returns 400 error (BEFORE behavior)."""
    response = client.get("/search?q=")
    assert response.status_code == 400
    assert "Search query parameter 'q' must be provided, or use filtering parameters" in response.json()["detail"]


def test_search_missing_term_no_filters(client: TestClient):
    """Test that missing search term without filters returns 400 error (BEFORE behavior)."""
    response = client.get("/search")
    assert response.status_code == 400
    assert "Search query parameter 'q' must be provided, or use filtering parameters" in response.json()["detail"]


def test_search_empty_term_with_facet_profile(client: TestClient, monkeypatch):
    """Test that empty search term with facet_profile is allowed (AFTER behavior)."""
    from rdflib import Graph

    # Mock the system graph with facet profile
    mock_system_graph = Graph()
    mock_system_graph.parse(
        data="""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix dcterms: <http://purl.org/dc/terms/> .
            @prefix prof: <http://www.w3.org/ns/dx/prof/> .
            @prefix prez: <https://prez.dev/> .
            @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

            <https://prez.dev/profile/facet-by-type>
                a prof:Profile , prez:ListingProfile ;
                dcterms:identifier "facet-type"^^xsd:token ;
                dcterms:title "Facet things by type" ;
                dcterms:description "Allows faceting by rdf:type" ;
                sh:property [ sh:path [ sh:union ( rdf:type ) ] ] .
        """,
        format="turtle",
    )

    # Add the mock data to the actual system graph
    from prez.cache import prez_system_graph

    prez_system_graph += mock_system_graph

    response = client.get("/search?q=&facet_profile=https://prez.dev/profile/facet-by-type&_mediatype=application/sparql-query")
    # Should not return 400 error about missing search term
    assert response.status_code != 400 or "Search query parameter 'q' must be provided" not in response.json().get("detail", "")


def test_search_empty_term_with_cql_filter(client: TestClient):
    """Test that empty search term with CQL filter is allowed (AFTER behavior)."""
    cql_filter = '{"op":"=","args":[{"property":"http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},"https://myclass"]}'
    response = client.get(f"/search?q=&filter={cql_filter}")
    # Should not return 400 error about missing search term
    assert response.status_code != 400 or "Search query parameter 'q' must be provided" not in response.json().get("detail", "")


def test_search_empty_term_with_bbox(client: TestClient):
    """Test that empty search term with bbox is allowed (AFTER behavior)."""
    response = client.get("/search?q=&bbox=113.338953078,-43.6345972634,153.569469029,-10.6681857235")
    # Should not return 400 error about missing search term
    assert response.status_code != 400 or "Search query parameter 'q' must be provided" not in response.json().get("detail", "")


def test_search_empty_term_with_datetime(client: TestClient):
    """Test that empty search term with datetime is allowed (AFTER behavior)."""
    response = client.get("/search?q=&datetime=2018-02-12T23:20:50Z/2018-03-18T12:31:12Z")
    # Should not return 400 error about missing search term
    assert response.status_code != 400 or "Search query parameter 'q' must be provided" not in response.json().get("detail", "")


def test_search_missing_term_with_facet_profile(client: TestClient, monkeypatch):
    """Test that missing search term with facet_profile is allowed (AFTER behavior)."""
    from rdflib import Graph

    # Mock the system graph with facet profile
    mock_system_graph = Graph()
    mock_system_graph.parse(
        data="""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix dcterms: <http://purl.org/dc/terms/> .
            @prefix prof: <http://www.w3.org/ns/dx/prof/> .
            @prefix prez: <https://prez.dev/> .
            @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

            <https://prez.dev/profile/facet-by-type>
                a prof:Profile , prez:ListingProfile ;
                dcterms:identifier "facet-type"^^xsd:token ;
                dcterms:title "Facet things by type" ;
                dcterms:description "Allows faceting by rdf:type" ;
                sh:property [ sh:path [ sh:union ( rdf:type ) ] ] .
        """,
        format="turtle",
    )

    # Add the mock data to the actual system graph
    from prez.cache import prez_system_graph

    prez_system_graph += mock_system_graph

    response = client.get("/search?facet_profile=https://prez.dev/profile/facet-by-type&_mediatype=text/turtle")
    # Should not return 400 error about missing search term
    assert response.status_code != 400 or "Search query parameter 'q' must be provided" not in response.json().get("detail", "")


def test_search_missing_term_with_cql_filter(client: TestClient):
    """Test that missing search term with CQL filter is allowed (AFTER behavior)."""
    cql_filter = '{"op":"=","args":[{"property":"http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},"feature"]}'
    response = client.get(f"/search?filter={cql_filter}")
    # Should not return 400 error about missing search term
    assert response.status_code != 400 or "Search query parameter 'q' must be provided" not in response.json().get("detail", "")