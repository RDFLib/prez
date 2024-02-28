from pathlib import Path

import pytest
from pyoxigraph import Store
from rdflib import Graph, URIRef

from prez.services.connegp_service import NegotiatedPMTs


@pytest.fixture(scope="module")
def test_store() -> Store:
    store = Store()
    profiles = Path(__file__).parent / "data" / "profiles" / "remote_profile.ttl"
    store.load(profiles, mime_type="text/turtle")
    return store


@pytest.fixture(scope="module")
def test_prefix_graph():
    graph = Graph(bind_namespaces="rdflib")
    graph.bind("ex", "https://example.com/")
    return graph


@pytest.mark.parametrize(
    "headers, params, classes, expected_selected",
    [
        [
            {"Accept-Profile": "<default>, <alternate>;q=0.9"},
            {"_media": "text/anot+turtle, text/turtle;q=0.9"},
            [URIRef("<http://www.w3.org/ns/dx/prof/profile>")],
            {
                "profile": "",
                "title": "",
                "mediatype": "",
                "class": ""
            }
        ],
    ]
)
@pytest.mark.asyncio
async def test_connegp(headers, params, classes, expected_selected, test_store, test_prefix_graph):
    pmts = NegotiatedPMTs(**{
        "headers": headers,
        "params": params,
        "classes": classes,
        "_system_store": test_store,
        "_prefix_graph": test_prefix_graph
    })
    success = await pmts.setup()

    assert pmts.selected == expected_selected
