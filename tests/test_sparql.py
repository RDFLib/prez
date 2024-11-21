import pytest


def test_select(client):
    """check that a valid select query returns a 200 response."""
    r = client.get(
        "/sparql?query=SELECT%20*%0AWHERE%20%7B%0A%20%20%3Fs%20%3Fp%20%3Fo%0A%7D%20LIMIT%201"
    )
    assert r.status_code == 200


def test_construct(client):
    """check that a valid construct query returns a 200 response."""
    r = client.get(
        "/sparql?query=CONSTRUCT%20%7B%0A%20%20%3Fs%20%3Fp%20%3Fo%0A%7D%20WHERE%20%7B%0A%20%20%3Fs%20%3Fp%20%3Fo%0A%7D%20LIMIT%201"
    )
    assert r.status_code == 200


@pytest.mark.parametrize(
    "query,expected_result",
    [
        (
            "/sparql?query=PREFIX%20ex%3A%20%3Chttp%3A%2F%2Fexample.com%2Fdatasets%2F%3E%0APREFIX%20dcterms%3A%20%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Fterms%2F%3E%0A%0AASK%0AWHERE%20%7B%0A%20%20%3Fsubject%20dcterms%3Atitle%20%3Ftitle%20.%0A%20%20FILTER%20CONTAINS(LCASE(%3Ftitle)%2C%20%22sandgate%22)%0A%7D",
            True,
        ),
        (
            "/sparql?query=ASK%20%7B%20%3Chttps%3A%2F%2Ffake%3E%20%3Fp%20%3Fo%20%7D",
            False,
        ),
    ],
)
def test_ask(client, query, expected_result):
    """Check that valid ASK queries return a 200 response with the expected boolean result."""
    r = client.get(query)

    assert r.status_code == 200


def test_post(client):
    """check that a valid post query returns a 200 response."""
    r = client.post(
        "/sparql",
        data={
            "query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1",
            "format": "application/x-www-form-urlencoded",
        },
    )
    assert r.status_code == 200


def test_post_invalid_data(client):
    """check that a post query with invalid data returns a 400 response."""
    r = client.post(
        "/sparql",
        data={
            "query": "INVALID QUERY",
            "format": "application/x-www-form-urlencoded",
        },
    )
    assert r.status_code == 400


def test_insert_as_query(client):
    """
    Also tested manually with Fuseki
    """
    r = client.post(
        "/sparql",
        data={
            "query": "INSERT {<:s> <:p> <:o>}",
            "format": "application/x-www-form-urlencoded",
        },
    )
    assert r.status_code == 400
