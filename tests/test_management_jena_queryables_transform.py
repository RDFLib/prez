from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from rdflib import DCTERMS, RDF, SH, XSD, Graph, Literal, URIRef

from prez.config import Settings
from prez.reference_data.prez_ns import ONT
from prez.routers.management import router as management_router
from prez.services.jena_assembler_queryables import (
    JenaAssemblerTransformError,
    transform_jena_assembler_to_queryables,
)


DIRECT_ASSEMBLER_TTL = """
@prefix : <http://example.com/assembler#> .
@prefix ex: <http://example.com/> .
@prefix field: <urn:test:field#> .
@prefix fuseki: <http://jena.apache.org/fuseki#> .
@prefix geosparql: <http://www.opengis.net/ont/geosparql#> .
@prefix idx: <urn:jena:lucene:index#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix text: <http://jena.apache.org/text#> .

:service a fuseki:Service ;
    fuseki:name "mining" ;
    fuseki:dataset :textDataset .

:textDataset a text:TextDataset ;
    text:dataset :baseDataset ;
    text:index :index .

:index a text:TextIndexShacl ;
    text:shapes ( :MiningReportShape ) .

field:commodity
    idx:fieldName "commodity" ;
    idx:fieldType idx:KeywordField ;
    idx:facetable true ;
    sh:path ex:commodity .

field:year
    idx:fieldName "year" ;
    idx:fieldType idx:IntField ;
    sh:path ex:year .

field:location
    idx:fieldName "location" ;
    idx:fieldType idx:LatLonField ;
    sh:path geosparql:asWKT .

:MiningReportShape
    sh:property field:commodity ;
    sh:property field:year ;
    sh:property [
        idx:fieldName "title" ;
        sh:path rdfs:label
    ] ;
    sh:property field:location .
"""


WRAPPED_ASSEMBLER_TTL = """
@prefix : <http://example.com/assembler#> .
@prefix ex: <http://example.com/> .
@prefix field: <urn:test:field#> .
@prefix fuseki: <http://jena.apache.org/fuseki#> .
@prefix geosparql: <http://jena.apache.org/geosparql#> .
@prefix idx: <urn:jena:lucene:index#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix text: <http://jena.apache.org/text#> .

:service a fuseki:Service ;
    fuseki:name "mining" ;
    fuseki:dataset :geoDataset .

:geoDataset a geosparql:GeosparqlDataset ;
    geosparql:dataset :textDataset .

:textDataset a text:TextDataset ;
    text:dataset :baseDataset ;
    text:index :index .

:index a text:TextIndexShacl ;
    text:shapes ( :MiningReportShape ) .

field:commodity
    idx:fieldName "commodity" ;
    idx:fieldType idx:KeywordField ;
    idx:facetable true ;
    sh:path ex:commodity .

:MiningReportShape
    sh:property field:commodity .
"""


def _graph_from_turtle(turtle: str) -> Graph:
    return Graph().parse(data=turtle, format="turtle")


def _build_management_app(runtime_settings: Settings) -> FastAPI:
    app = FastAPI()
    app.state.settings = runtime_settings
    app.include_router(management_router)
    return app


def test_transform_jena_assembler_to_queryables_generates_expected_fields():
    output_graph = transform_jena_assembler_to_queryables(
        _graph_from_turtle(DIRECT_ASSEMBLER_TTL),
        "mining",
    )

    commodity = URIRef("urn:test:field#commodity")
    year = URIRef("urn:test:field#year")
    title = URIRef("urn:jena:lucene:field#title")
    location = URIRef("urn:test:field#location")
    queryable_type = URIRef("http://www.opengis.net/doc/IS/cql2/1.0/Queryable")

    assert (commodity, RDF.type, queryable_type) in output_graph
    assert (commodity, DCTERMS.identifier, Literal(str(commodity))) in output_graph
    assert (commodity, SH.name, Literal("commodity")) in output_graph
    assert (commodity, SH.datatype, XSD.string) in output_graph
    assert (commodity, ONT.facetable, Literal(True)) in output_graph

    assert (year, RDF.type, queryable_type) in output_graph
    assert (year, SH.datatype, XSD.integer) in output_graph

    assert (title, RDF.type, queryable_type) in output_graph
    assert (title, DCTERMS.identifier, Literal(str(title))) in output_graph
    assert (title, SH.datatype, XSD.string) in output_graph

    assert (location, RDF.type, queryable_type) not in output_graph


def test_transform_jena_assembler_to_queryables_resolves_geosparql_wrapper():
    output_graph = transform_jena_assembler_to_queryables(
        _graph_from_turtle(WRAPPED_ASSEMBLER_TTL),
        "mining",
    )
    commodity = URIRef("urn:test:field#commodity")
    queryable_type = URIRef("http://www.opengis.net/doc/IS/cql2/1.0/Queryable")
    assert (commodity, RDF.type, queryable_type) in output_graph


def test_transform_jena_assembler_to_queryables_requires_matching_dataset_name():
    with pytest.raises(JenaAssemblerTransformError, match="fuseki:Service"):
        transform_jena_assembler_to_queryables(
            _graph_from_turtle(DIRECT_ASSEMBLER_TTL),
            "missing",
        )


def test_management_endpoint_returns_generated_turtle():
    app = _build_management_app(Settings(jena_fuseki_dataset_name="mining"))
    with TestClient(app) as client:
        response = client.post(
            "/jena-assembler-to-queryables",
            content=DIRECT_ASSEMBLER_TTL,
            headers={"content-type": "text/turtle"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/turtle")
    graph = Graph().parse(data=response.text, format="turtle")
    assert (
        URIRef("urn:test:field#commodity"),
        DCTERMS.identifier,
        Literal("urn:test:field#commodity"),
    ) in graph


def test_management_endpoint_rejects_invalid_turtle():
    app = _build_management_app(Settings(jena_fuseki_dataset_name="mining"))
    with TestClient(app) as client:
        response = client.post(
            "/jena-assembler-to-queryables",
            content="not valid turtle",
            headers={"content-type": "text/turtle"},
        )

    assert response.status_code == 400
    assert "Invalid Turtle body" in response.json()["detail"]


def test_management_endpoint_requires_text_turtle_content_type():
    app = _build_management_app(Settings(jena_fuseki_dataset_name="mining"))
    with TestClient(app) as client:
        response = client.post(
            "/jena-assembler-to-queryables",
            content=DIRECT_ASSEMBLER_TTL,
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 415
    assert response.json()["detail"] == "Content-Type must be text/turtle."


def test_management_endpoint_requires_configured_dataset_name():
    app = _build_management_app(Settings())
    with TestClient(app) as client:
        response = client.post(
            "/jena-assembler-to-queryables",
            content=DIRECT_ASSEMBLER_TTL,
            headers={"content-type": "text/turtle"},
        )

    assert response.status_code == 400
    assert "jena_fuseki_dataset_name" in response.json()["detail"]


def test_management_endpoint_errors_when_dataset_not_found():
    app = _build_management_app(Settings(jena_fuseki_dataset_name="other"))
    with TestClient(app) as client:
        response = client.post(
            "/jena-assembler-to-queryables",
            content=DIRECT_ASSEMBLER_TTL,
            headers={"content-type": "text/turtle"},
        )

    assert response.status_code == 400
    assert "No fuseki:Service" in response.json()["detail"]
