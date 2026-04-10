from pathlib import Path
from types import SimpleNamespace

import pytest
from pyoxigraph import RdfFormat, Store
from rdflib import DCTERMS, RDF, SH, Literal, URIRef

from prez.config import Settings
from prez.repositories import PyoxigraphRepo
from prez.services.app_service import retrieve_queryable_definitions


ASSEMBLER_TTL = """
@prefix : <http://example.com/assembler#> .
@prefix ex: <http://example.com/> .
@prefix field: <urn:test:field#> .
@prefix fuseki: <http://jena.apache.org/fuseki#> .
@prefix idx: <urn:jena:lucene:index#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix text: <http://jena.apache.org/text#> .

:service a fuseki:Service ;
    fuseki:name "mining" ;
    fuseki:dataset :textDataset .

:textDataset a text:TextDataset ;
    text:index :index .

:index a text:TextIndexShacl ;
    text:shapes ( :Shape ) .

field:commodity
    idx:fieldName "commodity" ;
    idx:fieldType idx:KeywordField ;
    idx:facetable true ;
    sh:path ex:commodity .

:Shape sh:property field:commodity .
"""


REMOTE_QUERYABLES_TTL = """
@prefix cql: <http://www.opengis.net/doc/IS/cql2/1.0/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix prez: <https://prez.dev/ont/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<https://example.com/queryables/remote-commodity>
    a cql:Queryable, sh:PropertyShape ;
    dcterms:identifier "urn:test:field#commodity" ;
    sh:name "Remote Commodity" ;
    sh:description "Remote definition wins over generated" ;
    sh:datatype xsd:string ;
    sh:path <http://example.com/remoteCommodity> ;
    prez:facetable false .
"""


LOCAL_QUERYABLES_TTL = """
@prefix cql: <http://www.opengis.net/doc/IS/cql2/1.0/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix prez: <https://prez.dev/ont/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<https://example.com/queryables/local-commodity>
    a cql:Queryable, sh:PropertyShape ;
    dcterms:identifier "urn:test:field#commodity" ;
    sh:name "Local Commodity" ;
    sh:description "Local definition wins over remote and generated" ;
    sh:datatype xsd:string ;
    sh:path <http://example.com/localCommodity> ;
    prez:facetable true .
"""


QUERYABLE_TYPE = URIRef("http://www.opengis.net/doc/IS/cql2/1.0/Queryable")
PREZ_FACETABLE = URIRef("https://prez.dev/ont/facetable")


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.mark.asyncio
async def test_retrieve_queryable_definitions_merges_sources_with_precedence(
    monkeypatch,
    tmp_path,
):
    assembler_path = tmp_path / "config.ttl"
    reference_data_dir = tmp_path / "reference_data"
    _write_file(assembler_path, ASSEMBLER_TTL)
    _write_file(reference_data_dir / "queryables" / "local.ttl", LOCAL_QUERYABLES_TTL)
    monkeypatch.setenv("PREZ_REFERENCE_DATA_DIR", str(reference_data_dir))

    remote_store = Store()
    remote_store.load(REMOTE_QUERYABLES_TTL.encode("utf-8"), RdfFormat.TURTLE)
    app_state = SimpleNamespace(
        settings=Settings(
            _env_file=None,
            enable_cql_jena_lucene_json=False,
            jena_assembler_path=str(assembler_path),
        ),
        repo=PyoxigraphRepo(remote_store),
        queryable_props={},
    )
    system_store = Store()

    await retrieve_queryable_definitions(app_state, system_store)

    assert app_state.queryable_props == {
        "urn:test:field#commodity": "https://example.com/queryables/local-commodity"
    }

    system_graph = await PyoxigraphRepo(system_store).rdf_query_to_rdflib_graph(
        "DESCRIBE ?queryable WHERE { ?queryable a <http://www.opengis.net/doc/IS/cql2/1.0/Queryable> }"
    )
    local_queryable = URIRef("https://example.com/queryables/local-commodity")
    remote_queryable = URIRef("https://example.com/queryables/remote-commodity")
    generated_queryable = URIRef("urn:test:field#commodity")

    assert (local_queryable, RDF.type, QUERYABLE_TYPE) in system_graph
    assert (local_queryable, SH.name, Literal("Local Commodity")) in system_graph
    assert (local_queryable, PREZ_FACETABLE, Literal(True)) in system_graph

    assert (remote_queryable, RDF.type, QUERYABLE_TYPE) not in system_graph
    assert (generated_queryable, RDF.type, QUERYABLE_TYPE) not in system_graph


@pytest.mark.asyncio
async def test_retrieve_queryable_definitions_uses_generated_queryables_when_unshadowed(
    monkeypatch,
    tmp_path,
):
    assembler_path = tmp_path / "config.ttl"
    reference_data_dir = tmp_path / "reference_data"
    _write_file(assembler_path, ASSEMBLER_TTL)
    (reference_data_dir / "queryables").mkdir(parents=True)
    monkeypatch.setenv("PREZ_REFERENCE_DATA_DIR", str(reference_data_dir))

    app_state = SimpleNamespace(
        settings=Settings(
            _env_file=None,
            enable_cql_jena_lucene_json=False,
            jena_assembler_path=str(assembler_path),
        ),
        repo=PyoxigraphRepo(Store()),
        queryable_props={},
    )
    system_store = Store()

    await retrieve_queryable_definitions(app_state, system_store)

    generated_queryable = URIRef("urn:test:field#commodity")
    system_graph = await PyoxigraphRepo(system_store).rdf_query_to_rdflib_graph(
        "DESCRIBE ?queryable WHERE { ?queryable a <http://www.opengis.net/doc/IS/cql2/1.0/Queryable> }"
    )

    assert app_state.queryable_props == {
        "urn:test:field#commodity": "urn:test:field#commodity"
    }
    assert (generated_queryable, RDF.type, QUERYABLE_TYPE) in system_graph
    assert (generated_queryable, DCTERMS.identifier, Literal("urn:test:field#commodity")) in system_graph
    assert (generated_queryable, SH.path, URIRef("http://example.com/commodity")) in system_graph
