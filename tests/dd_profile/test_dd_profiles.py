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
            "/v/collection?_profile=prfl:dd&_mediatype=application/json",
            [
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/pggd",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Borehole purposes applicable to regulatory notification forms."
                    ],
                    "http://purl.org/dc/terms/publisher": [],
                    "http://purl.org/linked-data/registry#status": [],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["PGGD selection"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                        "http://www.w3.org/2004/02/skos/core#Collection"
                    ],
                },
                {
                    "@id": "http://linked.data.gov.au/def/depth-reference/absolute",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "A fixed plane or point that describes an absolute reference for depth observations."
                    ],
                    "http://purl.org/dc/terms/publisher": [],
                    "http://purl.org/linked-data/registry#status": [],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Absolute"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                        "http://www.w3.org/2004/02/skos/core#Collection"
                    ],
                },
                {
                    "@id": "http://resource.geosciml.org/classifier/cgi/contacttype",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "All Concepts in this vocabulary"
                    ],
                    "http://purl.org/dc/terms/publisher": [],
                    "http://purl.org/linked-data/registry#status": [],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Contact Type - All Concepts"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [
                        "http://www.w3.org/2004/02/skos/core#Collection"
                    ],
                },
            ],
        ],
    ],
)
def test_vocab_listing(test_client: TestClient, url: str, expected_data: list):
    with test_client as client:
        response = client.get(url)
        assert response.json() == expected_data


@pytest.mark.parametrize(
    "iri, expected_data",
    [
        [
            "http://linked.data.gov.au/def2/borehole-purpose",
            [
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/carbon-capture-and-storage",
                    "http://www.w3.org/2004/02/skos/core#broader": [
                        "http://linked.data.gov.au/def/borehole-purpose/greenhouse-gas-storage"
                    ],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells that deposit carbon dioxide into an underground geological formation after capture from large point sources, such as a cement factory or biomass power plant."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Carbon Capture and Storage"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/coal",
                    "http://www.w3.org/2004/02/skos/core#broader": [],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells and bores drilled to facilitate the mining of coal under permits governed by the Queensland Mineral Resources Act 1989"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Coal"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/coal-seam-gas",
                    "http://www.w3.org/2004/02/skos/core#broader": [
                        "http://linked.data.gov.au/def/borehole-purpose/petroleum"
                    ],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells targetting coal seams where hydrocarbons are kept in place via adsorption to the coal surface and hydrostatic pressure"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Coal Seam Gas"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/conventional-petroleum",
                    "http://www.w3.org/2004/02/skos/core#broader": [
                        "http://linked.data.gov.au/def/borehole-purpose/petroleum"
                    ],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells targetting conventional petroleum reservoirs where buoyant forces keep hydrocarbons in place below a sealing caprock."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Conventional Petroleum"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/geothermal",
                    "http://www.w3.org/2004/02/skos/core#broader": [],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells and bores drilled under permits governed by the Queensland Geothermal Energy Act 2010"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Geothermal"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/greenhouse-gas-storage",
                    "http://www.w3.org/2004/02/skos/core#broader": [],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells and bores drilled under permits governed by the Queensland Greenhouse Gas Storage Act 2009"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Greenhouse Gas Storage"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/mineral",
                    "http://www.w3.org/2004/02/skos/core#broader": [],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells and bores drilled to facilitate the mining of minerals, excluding coal and oil shale, under permits governed by the Queensland Mineral Resources Act (1989)"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Mineral"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/non-industry",
                    "http://www.w3.org/2004/02/skos/core#broader": [],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells and bores drilled by non-industry agents outside of the State Resources Acts"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Non-Industry"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/oil-shale",
                    "http://www.w3.org/2004/02/skos/core#broader": [],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells and bores drilled to facilitate the mining of oil shale under permits governed by the Queensland Mineral Resources Act 1989"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Oil Shale"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/open-cut-coal-mining",
                    "http://www.w3.org/2004/02/skos/core#broader": [
                        "http://linked.data.gov.au/def/borehole-purpose/coal"
                    ],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells drilled for the purpose of assessing coal resources for an open cut coal mine."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Open-Cut Coal Mining"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/petroleum",
                    "http://www.w3.org/2004/02/skos/core#broader": [],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells and bores drilled under permits governed by the Queensland Petroleum Act 1923 and Petroleum and Gas (Production and Safety) Act 2004. This includes water observation, water disposal, and water supply wells drilled under the relevant Petroleum Acts rather than the Water Act."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Petroleum"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/shale-gas",
                    "http://www.w3.org/2004/02/skos/core#broader": [
                        "http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum"
                    ],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells targetting shale that produces natural gas. A shale that is thermally mature enough and has sufficient gas content to produce economic quantities of natural gas."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Shale Gas"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/shale-oil",
                    "http://www.w3.org/2004/02/skos/core#broader": [
                        "http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum"
                    ],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells targetting shale that produces oil. Oil obtained by artificial maturation of oil shale. The process of artificial maturation uses controlled heating, or pyrolysis, of kerogen to release the shale oil."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Shale Oil"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/tight-gas",
                    "http://www.w3.org/2004/02/skos/core#broader": [
                        "http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum"
                    ],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells targetting gas from relatively impermeable reservoir rock."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Tight Gas"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/tight-oil",
                    "http://www.w3.org/2004/02/skos/core#broader": [
                        "http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum"
                    ],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells targetting oil from relatively impermeable reservoir rock."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Tight Oil"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum",
                    "http://www.w3.org/2004/02/skos/core#broader": [
                        "http://linked.data.gov.au/def/borehole-purpose/petroleum"
                    ],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells targetting unconventional reservoirs whose properties including porosity, permeability, or trapping mechanism differ from conventional reservoirs"
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Unconventional Petroleum"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/underground-coal-mining",
                    "http://www.w3.org/2004/02/skos/core#broader": [
                        "http://linked.data.gov.au/def/borehole-purpose/coal"
                    ],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells drilled for the purpose of assessing coal resources for an underground coal mine."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Underground Coal Mining"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/borehole-purpose/water",
                    "http://www.w3.org/2004/02/skos/core#broader": [],
                    "http://www.w3.org/2004/02/skos/core#narrower": [],
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "Wells and bores drilled under permits governed by the Queensland Water Act 2000. A well or bore is only considered a water well or bore where drilled under the Water Act, e.g. a well or bore drilled to serve a water observation function under the Petroleum Act is considered a Petroleum Well with an Observation function or sub-purpose. Additional rights, obligations, and responsibilities may be conferred by intersecting legislation on wells and bores drilled by mineral and coal permit holders and petroleum and gas permit holders under the Mineral Resources Act 1989 and the Petroleum and Gas (Production and Safety) Act 2004 respectively."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Water"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
            ],
        ],
        [
            "http://linked.data.gov.au/def/depth-reference/absolute",
            [
                {
                    "@id": "http://linked.data.gov.au/def/depth-reference/australian-height-datum",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "The Australian Height Datum is a vertical datum in Australia.In 1971 the mean sea level for 1966-1968 was assigned the value of 0.000m on the Australian Height Datum at thirty tide gauges around the coast of the Australian continent."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": [
                        "Australian Height Datum"
                    ],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/depth-reference/mean-sea-level",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "The elevation (on the ground) or altitude (in the air) of an object, relative to the average sea level."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Mean Sea Level"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
                {
                    "@id": "http://linked.data.gov.au/def/depth-reference/metres-sub-sea",
                    "http://www.w3.org/2004/02/skos/core#definition": [
                        "The distance below mean sea level, the inverse of measurements to Mean Sea Level."
                    ],
                    "http://www.w3.org/2004/02/skos/core#prefLabel": ["Metres Sub-Sea"],
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": [],
                },
            ],
        ],
    ],
)
def test_vocab_object(test_client: TestClient, iri: str, expected_data: list):
    with test_client as client:
        response = client.get(f"/object?uri={iri}&_profile=prfl:dd")
        print(response.json())
        assert response.json() == expected_data
