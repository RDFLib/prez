import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyoxigraph.pyoxigraph import Store

from prez.app import app
from prez.dependencies import get_repo
from prez.sparql.methods import Repo, PyoxigraphRepo


@pytest.fixture(scope="session")
def test_store() -> Store:
    # Create a new pyoxigraph Store
    store = Store()

    for file in Path(__file__).parent.glob("../tests/data/*/input/*.ttl"):
        store.load(file.read_bytes(), "text/turtle")

    return store


@pytest.fixture(scope="session")
def test_repo(test_store: Store) -> Repo:
    # Create a PyoxigraphQuerySender using the test_store
    return PyoxigraphRepo(test_store)


@pytest.fixture(scope="session")
def test_client(test_repo: Repo) -> TestClient:
    # Override the dependency to use the test_repo
    def override_get_repo():
        return test_repo

    app.dependency_overrides[get_repo] = override_get_repo

    with TestClient(app) as c:
        yield c

    # Remove the override to ensure subsequent tests are unaffected
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "url, mediatype, expected_data",
    [
        [
            "/v/vocab?_profile=prfl:dd&_mediatype=",
            "application/json",
            {
                "@context": {
                    "iri": "@id",
                    "definition": "http://www.w3.org/2004/02/skos/core#definition",
                    "publisher": "http://purl.org/dc/terms/publisher",
                    "status": "http://purl.org/linked-data/registry#status",
                    "prefLabel": "http://www.w3.org/2004/02/skos/core#prefLabel",
                },
                "@graph": [
                    {
                        "iri": "http://data.bgs.ac.uk/ref/BeddingSurfaceStructure",
                        "definition": "A dictionary of bed surface structures, eg. ripples, dessication cracks.",
                        "publisher": None,
                        "status": "https://linked.data.gov.au/def/reg-statuses/experimental",
                        "prefLabel": "BeddingSurfaceStructure",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def2/borehole-purpose",
                        "definition": "The primary purpose of a borehole based on the legislative State Act and/or the resources industry sector.",
                        "publisher": None,
                        "status": "https://linked.data.gov.au/def/reg-statuses/stable",
                        "prefLabel": "Borehole Purpose",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def2/borehole-purpose-no-children",
                        "definition": "The primary purpose of a borehole based on the legislative State Act and/or the resources industry sector.",
                        "publisher": None,
                        "status": "https://linked.data.gov.au/def/reg-statuses/stable",
                        "prefLabel": "Borehole Purpose no children",
                    },
                    {
                        "iri": "http://resource.geosciml.org/classifierscheme/cgi/2016.01/contacttype",
                        "definition": "This scheme describes the concept space for Contact Type concepts, as defined by the IUGS Commission for Geoscience Information (CGI) Geoscience Terminology Working Group. By extension, it includes all concepts in this conceptScheme, as well as concepts in any previous versions of the scheme. Designed for use in the contactType property in GeoSciML Contact elements.",
                        "publisher": None,
                        "status": None,
                        "prefLabel": "Contact Type",
                    },
                    {
                        "iri": "https://linked.data.gov.au/def/reg-statuses",
                        "definition": "This vocabulary is a re-published and only marginally changed version of the Registry Ontology's (http://epimorphics.com/public/vocabulary/Registry.html) *Status* vocabulary (online in RDF: http://purl.org/linked-data/registry). The only real change to content has been the addition of the term `unstable`. This re-publication has been performed to allow the IRIs of each vocab term (skos:Concept) to resolve to both human-readable and machine-readable forms of content (HTML and RDF), using HTTP content negotiation.\n\nNote that just like the original form of this vocabulary, while it is a SKOS vocabulary implemented as a single skos:ConceptScheme, it is also an OWL Ontology and that each *Status* is both a skos:Concept and a reg:Status individual.",
                        "publisher": None,
                        "status": None,
                        "prefLabel": "Registry Status Vocabulary",
                    },
                    {
                        "iri": "https://linked.data.gov.au/def/vocdermods",
                        "definition": "The modes by which one vocabulary may derive from another",
                        "publisher": None,
                        "status": "https://linked.data.gov.au/def/reg-statuses/stable",
                        "prefLabel": "Vocabulary Derivation Modes",
                    },
                    {
                        "iri": "https://linked.data.gov.au/def/warox-alteration-types",
                        "definition": "This vocabulary give Alteration Type concepts, listed in the Geologicla Survey of Western Australia's WAROX database.",
                        "publisher": None,
                        "status": None,
                        "prefLabel": "WAROX Alteration Type",
                    },
                ],
            },
        ],
        [
            "/v/collection?_profile=prfl:dd&_mediatype=",
            "application/json",
            {
                "@context": {
                    "iri": "@id",
                    "definition": "http://www.w3.org/2004/02/skos/core#definition",
                    "publisher": "http://purl.org/dc/terms/publisher",
                    "status": "http://purl.org/linked-data/registry#status",
                    "prefLabel": "http://www.w3.org/2004/02/skos/core#prefLabel",
                },
                "@graph": [
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/pggd",
                        "definition": "Borehole purposes applicable to regulatory notification forms.",
                        "publisher": None,
                        "status": None,
                        "prefLabel": "PGGD selection",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/depth-reference/absolute",
                        "definition": "A fixed plane or point that describes an absolute reference for depth observations.",
                        "publisher": None,
                        "status": None,
                        "prefLabel": "Absolute",
                    },
                    {
                        "iri": "http://resource.geosciml.org/classifier/cgi/contacttype",
                        "definition": "All Concepts in this vocabulary",
                        "publisher": None,
                        "status": None,
                        "prefLabel": "Contact Type - All Concepts",
                    },
                ],
            },
        ],
        [
            "/v/vocab?_profile=prfl:dd&_mediatype=",
            "text/csv",
            r"""iri,definition,publisher,status,prefLabel
http://data.bgs.ac.uk/ref/BeddingSurfaceStructure,"A dictionary of bed surface structures, eg. ripples, dessication cracks.",,https://linked.data.gov.au/def/reg-statuses/experimental,BeddingSurfaceStructure
http://linked.data.gov.au/def2/borehole-purpose,The primary purpose of a borehole based on the legislative State Act and/or the resources industry sector.,,https://linked.data.gov.au/def/reg-statuses/stable,Borehole Purpose
http://linked.data.gov.au/def2/borehole-purpose-no-children,The primary purpose of a borehole based on the legislative State Act and/or the resources industry sector.,,https://linked.data.gov.au/def/reg-statuses/stable,Borehole Purpose no children
http://resource.geosciml.org/classifierscheme/cgi/2016.01/contacttype,"This scheme describes the concept space for Contact Type concepts, as defined by the IUGS Commission for Geoscience Information (CGI) Geoscience Terminology Working Group. By extension, it includes all concepts in this conceptScheme, as well as concepts in any previous versions of the scheme. Designed for use in the contactType property in GeoSciML Contact elements.",,,Contact Type
https://linked.data.gov.au/def/reg-statuses,"This vocabulary is a re-published and only marginally changed version of the Registry Ontology's (http://epimorphics.com/public/vocabulary/Registry.html) *Status* vocabulary (online in RDF: http://purl.org/linked-data/registry). The only real change to content has been the addition of the term `unstable`. This re-publication has been performed to allow the IRIs of each vocab term (skos:Concept) to resolve to both human-readable and machine-readable forms of content (HTML and RDF), using HTTP content negotiation.

Note that just like the original form of this vocabulary, while it is a SKOS vocabulary implemented as a single skos:ConceptScheme, it is also an OWL Ontology and that each *Status* is both a skos:Concept and a reg:Status individual.",,,Registry Status Vocabulary
https://linked.data.gov.au/def/vocdermods,The modes by which one vocabulary may derive from another,,https://linked.data.gov.au/def/reg-statuses/stable,Vocabulary Derivation Modes
https://linked.data.gov.au/def/warox-alteration-types,"This vocabulary give Alteration Type concepts, listed in the Geologicla Survey of Western Australia's WAROX database.",,,WAROX Alteration Type
""",
        ],
        [
            "/v/collection?_profile=prfl:dd&_mediatype=",
            "text/csv",
            """iri,definition,publisher,status,prefLabel
http://linked.data.gov.au/def/borehole-purpose/pggd,Borehole purposes applicable to regulatory notification forms.,,,PGGD selection
http://linked.data.gov.au/def/depth-reference/absolute,A fixed plane or point that describes an absolute reference for depth observations.,,,Absolute
http://resource.geosciml.org/classifier/cgi/contacttype,All Concepts in this vocabulary,,,Contact Type - All Concepts
""",
        ],
    ],
)
def test_vocab_listing(
    test_client: TestClient, url: str, mediatype: str, expected_data: list | str
):
    response = test_client.get(f"{url}{mediatype}")
    if mediatype == "application/json":
        assert response.json() == expected_data
    elif mediatype == "text/csv":
        expected_data_reader = list(csv.reader(io.StringIO(expected_data)))
        actual_data_reader = list(csv.reader(io.StringIO(response.text)))
        assert expected_data_reader == actual_data_reader
    else:
        assert response.text == expected_data


@pytest.mark.parametrize(
    "iri, mediatype, expected_data",
    [
        [
            "http://linked.data.gov.au/def2/borehole-purpose",
            "application/json",
            {
                "@context": {
                    "iri": "@id",
                    "broader": "http://www.w3.org/2004/02/skos/core#broader",
                    "prefLabel": "http://www.w3.org/2004/02/skos/core#prefLabel",
                },
                "@graph": [
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/carbon-capture-and-storage",
                        "broader": "http://linked.data.gov.au/def/borehole-purpose/greenhouse-gas-storage",
                        "prefLabel": "Carbon Capture and Storage",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/coal",
                        "broader": None,
                        "prefLabel": "Coal",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/coal-seam-gas",
                        "broader": "http://linked.data.gov.au/def/borehole-purpose/petroleum",
                        "prefLabel": "Coal Seam Gas",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/conventional-petroleum",
                        "broader": "http://linked.data.gov.au/def/borehole-purpose/petroleum",
                        "prefLabel": "Conventional Petroleum",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/geothermal",
                        "broader": None,
                        "prefLabel": "Geothermal",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/greenhouse-gas-storage",
                        "broader": None,
                        "prefLabel": "Greenhouse Gas Storage",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/mineral",
                        "broader": None,
                        "prefLabel": "Mineral",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/non-industry",
                        "broader": None,
                        "prefLabel": "Non-Industry",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/oil-shale",
                        "broader": None,
                        "prefLabel": "Oil Shale",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/open-cut-coal-mining",
                        "broader": "http://linked.data.gov.au/def/borehole-purpose/coal",
                        "prefLabel": "Open-Cut Coal Mining",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/petroleum",
                        "broader": None,
                        "prefLabel": "Petroleum",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/shale-gas",
                        "broader": "http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum",
                        "prefLabel": "Shale Gas",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/shale-oil",
                        "broader": "http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum",
                        "prefLabel": "Shale Oil",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/tight-gas",
                        "broader": "http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum",
                        "prefLabel": "Tight Gas",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/tight-oil",
                        "broader": "http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum",
                        "prefLabel": "Tight Oil",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum",
                        "broader": "http://linked.data.gov.au/def/borehole-purpose/petroleum",
                        "prefLabel": "Unconventional Petroleum",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/underground-coal-mining",
                        "broader": "http://linked.data.gov.au/def/borehole-purpose/coal",
                        "prefLabel": "Underground Coal Mining",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/borehole-purpose/water",
                        "broader": None,
                        "prefLabel": "Water",
                    },
                ],
            },
        ],
        [
            "http://linked.data.gov.au/def/depth-reference/absolute",
            "application/json",
            {
                "@context": {
                    "iri": "@id",
                    "definition": "http://www.w3.org/2004/02/skos/core#definition",
                    "prefLabel": "http://www.w3.org/2004/02/skos/core#prefLabel",
                },
                "@graph": [
                    {
                        "iri": "http://linked.data.gov.au/def/depth-reference/australian-height-datum",
                        "definition": "The Australian Height Datum is a vertical datum in Australia.In 1971 the mean sea level for 1966-1968 was assigned the value of 0.000m on the Australian Height Datum at thirty tide gauges around the coast of the Australian continent.",
                        "prefLabel": "Australian Height Datum",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/depth-reference/mean-sea-level",
                        "definition": "The elevation (on the ground) or altitude (in the air) of an object, relative to the average sea level.",
                        "prefLabel": "Mean Sea Level",
                    },
                    {
                        "iri": "http://linked.data.gov.au/def/depth-reference/metres-sub-sea",
                        "definition": "The distance below mean sea level, the inverse of measurements to Mean Sea Level.",
                        "prefLabel": "Metres Sub-Sea",
                    },
                ],
            },
        ],
        [
            "http://linked.data.gov.au/def2/borehole-purpose",
            "text/csv",
            """iri,broader,prefLabel
http://linked.data.gov.au/def/borehole-purpose/carbon-capture-and-storage,http://linked.data.gov.au/def/borehole-purpose/greenhouse-gas-storage,Carbon Capture and Storage
http://linked.data.gov.au/def/borehole-purpose/coal,,Coal
http://linked.data.gov.au/def/borehole-purpose/coal-seam-gas,http://linked.data.gov.au/def/borehole-purpose/petroleum,Coal Seam Gas
http://linked.data.gov.au/def/borehole-purpose/conventional-petroleum,http://linked.data.gov.au/def/borehole-purpose/petroleum,Conventional Petroleum
http://linked.data.gov.au/def/borehole-purpose/geothermal,,Geothermal
http://linked.data.gov.au/def/borehole-purpose/greenhouse-gas-storage,,Greenhouse Gas Storage
http://linked.data.gov.au/def/borehole-purpose/mineral,,Mineral
http://linked.data.gov.au/def/borehole-purpose/non-industry,,Non-Industry
http://linked.data.gov.au/def/borehole-purpose/oil-shale,,Oil Shale
http://linked.data.gov.au/def/borehole-purpose/open-cut-coal-mining,http://linked.data.gov.au/def/borehole-purpose/coal,Open-Cut Coal Mining
http://linked.data.gov.au/def/borehole-purpose/petroleum,,Petroleum
http://linked.data.gov.au/def/borehole-purpose/shale-gas,http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum,Shale Gas
http://linked.data.gov.au/def/borehole-purpose/shale-oil,http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum,Shale Oil
http://linked.data.gov.au/def/borehole-purpose/tight-gas,http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum,Tight Gas
http://linked.data.gov.au/def/borehole-purpose/tight-oil,http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum,Tight Oil
http://linked.data.gov.au/def/borehole-purpose/unconventional-petroleum,http://linked.data.gov.au/def/borehole-purpose/petroleum,Unconventional Petroleum
http://linked.data.gov.au/def/borehole-purpose/underground-coal-mining,http://linked.data.gov.au/def/borehole-purpose/coal,Underground Coal Mining
http://linked.data.gov.au/def/borehole-purpose/water,,Water
""",
        ],
        [
            "http://linked.data.gov.au/def/depth-reference/absolute",
            "text/csv",
            """iri,definition,prefLabel
http://linked.data.gov.au/def/depth-reference/australian-height-datum,The Australian Height Datum is a vertical datum in Australia.In 1971 the mean sea level for 1966-1968 was assigned the value of 0.000m on the Australian Height Datum at thirty tide gauges around the coast of the Australian continent.,Australian Height Datum
http://linked.data.gov.au/def/depth-reference/mean-sea-level,"The elevation (on the ground) or altitude (in the air) of an object, relative to the average sea level.",Mean Sea Level
http://linked.data.gov.au/def/depth-reference/metres-sub-sea,"The distance below mean sea level, the inverse of measurements to Mean Sea Level.",Metres Sub-Sea
""",
        ],
    ],
)
def test_vocab_object(
    test_client: TestClient, iri: str, mediatype: str, expected_data: list | str
):
    response = test_client.get(
        f"/object?uri={iri}&_profile=prfl:dd&_mediatype={mediatype}"
    )
    if mediatype == "application/json":
        assert response.json() == expected_data
    elif mediatype == "text/csv":
        expected_data_reader = list(csv.reader(io.StringIO(expected_data)))
        actual_data_reader = list(csv.reader(io.StringIO(response.text)))
        assert expected_data_reader == actual_data_reader
    else:
        assert response.text == expected_data
