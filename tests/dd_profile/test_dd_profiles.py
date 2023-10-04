import os
import subprocess
from time import sleep

import pytest
from fastapi.testclient import TestClient

PREZ_DIR = os.getenv("PREZ_DIR")
LOCAL_SPARQL_STORE = os.getenv("LOCAL_SPARQL_STORE")


@pytest.fixture(scope="module")
def test_client(request):
    print("Run Local SPARQL Store")
    p1 = subprocess.Popen(["python", str(LOCAL_SPARQL_STORE), "-p", "3031"])
    sleep(1)

    def teardown():
        print("\nDoing teardown")
        p1.kill()

    request.addfinalizer(teardown)

    # must only import app after config.py has been altered above so config is retained
    from prez.app import app

    return TestClient(app)


@pytest.mark.parametrize(
    "url, expected_data",
    [
        [
            "/v/vocab?_profile=prfl:dd&_mediatype=application/json",
            [
                {
                    "@id": "http://data.bgs.ac.uk/ref/BeddingSurfaceStructure",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "A dictionary of bed surface structures, eg. ripples, dessication cracks."
                    ],
                    "http://purl.org/dc/terms/publisher": [],
                    "http://purl.org/linked-data/registry#status": [
                        "https://linked.data.gov.au/def/reg-statuses/experimental"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "BeddingSurfaceStructure"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                        "http://www.w3.org/2004/02/skos/core#ConceptScheme"
                    ],
                },
                {
                    "@id": "http://linked.data.gov.au/def2/borehole-purpose",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "The primary purpose of a borehole based on the legislative State Act and/or the resources industry sector."
                    ],
                    "http://purl.org/dc/terms/publisher": [],
                    "http://purl.org/linked-data/registry#status": [
                        "https://linked.data.gov.au/def/reg-statuses/stable"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Borehole Purpose"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                        "http://www.w3.org/2004/02/skos/core#ConceptScheme"
                    ],
                },
                {
                    "@id": "http://linked.data.gov.au/def2/borehole-purpose-no-children",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "The primary purpose of a borehole based on the legislative State Act and/or the resources industry sector."
                    ],
                    "http://purl.org/dc/terms/publisher": [],
                    "http://purl.org/linked-data/registry#status": [
                        "https://linked.data.gov.au/def/reg-statuses/stable"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Borehole Purpose no children"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                        "http://www.w3.org/2004/02/skos/core#ConceptScheme"
                    ],
                },
                {
                    "@id": "http://resource.geosciml.org/classifierscheme/cgi/2016.01/contacttype",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "This scheme describes the concept space for Contact Type concepts, as defined by the IUGS Commission for Geoscience Information (CGI) Geoscience Terminology Working Group. By extension, it includes all concepts in this conceptScheme, as well as concepts in any previous versions of the scheme. Designed for use in the contactType property in GeoSciML Contact elements."
                    ],
                    "http://purl.org/dc/terms/publisher": [],
                    "http://purl.org/linked-data/registry#status": [],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Contact Type"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                        "http://www.w3.org/2004/02/skos/core#ConceptScheme"
                    ],
                },
                {
                    "@id": "https://linked.data.gov.au/def/reg-statuses",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "This vocabulary is a re-published and only marginally changed version of the Registry Ontology's (http://epimorphics.com/public/vocabulary/Registry.html) *Status* vocabulary (online in RDF: http://purl.org/linked-data/registry). The only real change to content has been the addition of the term `unstable`. This re-publication has been performed to allow the IRIs of each vocab term (skos:Concept) to resolve to both human-readable and machine-readable forms of content (HTML and RDF), using HTTP content negotiation.\n\nNote that just like the original form of this vocabulary, while it is a SKOS vocabulary implemented as a single skos:ConceptScheme, it is also an OWL Ontology and that each *Status* is both a skos:Concept and a reg:Status individual."
                    ],
                    "http://purl.org/dc/terms/publisher": [],
                    "http://purl.org/linked-data/registry#status": [],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Registry Status Vocabulary"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                        "http://www.w3.org/2004/02/skos/core#ConceptScheme"
                    ],
                },
                {
                    "@id": "https://linked.data.gov.au/def/vocdermods",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "The modes by which one vocabulary may derive from another"
                    ],
                    "http://purl.org/dc/terms/publisher": [],
                    "http://purl.org/linked-data/registry#status": [
                        "https://linked.data.gov.au/def/reg-statuses/stable"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Vocabulary Derivation Modes"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                        "http://www.w3.org/2004/02/skos/core#ConceptScheme"
                    ],
                },
                {
                    "@id": "https://linked.data.gov.au/def/warox-alteration-types",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "This vocabulary give Alteration Type concepts, listed in the Geologicla Survey of Western Australia's WAROX database."
                    ],
                    "http://purl.org/dc/terms/publisher": [],
                    "http://purl.org/linked-data/registry#status": [],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "WAROX Alteration Type"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                        "http://www.w3.org/2004/02/skos/core#ConceptScheme"
                    ],
                },
            ],
        ],
        [
            "/v/vocab/"
        ]
    ],
)
def test_vocab_listing(test_client: TestClient, url: str, expected_data: dict):
    with test_client as client:
        response = client.get(url)
        assert response.json() == expected_data
