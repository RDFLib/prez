import pytest
from prez.services.query_generation.cql import CQLParser
from prez.config import settings
from rdflib import Namespace, URIRef
from rdflib.namespace import GEO
from sparql_grammar_pydantic import IRI, Var, RDFLiteral, TriplesSameSubjectPath


# Temporarily set spatial_query_format to "graphdb" for testing
@pytest.fixture(autouse=True)
def set_graphdb_spatial_format():
    original_format = settings.spatial_query_format
    settings.spatial_query_format = "graphdb"
    yield
    settings.spatial_query_format = original_format


def test_cql_spatial_graphdb_intersects():
    cql_json = {
        "op": "s_intersects",
        "args": [
            {"property": "geometry"},
            {"type": "Point", "coordinates": [150.0, -30.0]},
        ],
    }
    parser = CQLParser(
        cql_json=cql_json, crs="http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    )
    parser.parse()

    expected_tssp1 = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=str(GEO.hasGeometry)),
        object=Var(value="geom_bnode"),
    )
    expected_tssp2 = TriplesSameSubjectPath.from_spo(
        subject=Var(value="geom_bnode"),
        predicate=IRI(value=str(GEO.asWKT)),
        object=Var(value="geom_var"),
    )
    expected_tssp3 = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=str(GEO.sfIntersects)),
        object=RDFLiteral(
            value="<http://www.opengis.net/def/crs/OGC/1.3/CRS84> POINT (150.0 -30.0)",
            datatype=IRI(value=str(GEO.wktLiteral)),
        ),
    )
    expected_tssp_list = {
        expected_tssp1.to_string(),
        expected_tssp2.to_string(),
        expected_tssp3.to_string(),
    }
    for tssp in parser.tssp_list:
        tssp_string = tssp.to_string()
        assert tssp_string in expected_tssp_list


def test_cql_spatial_graphdb_within_with_crs():
    cql_json = {
        "op": "s_within",
        "args": [
            {"property": "geometry"},
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [100.0, 0.0],
                        [101.0, 0.0],
                        [101.0, 1.0],
                        [100.0, 1.0],
                        [100.0, 0.0],
                    ]
                ],
            },
        ],
    }
    parser = CQLParser(
        cql_json=cql_json, crs="http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    )
    parser.parse()

    expected_wkt = "<http://www.opengis.net/def/crs/OGC/1.3/CRS84> POLYGON ((100.0 0.0, 101.0 0.0, 101.0 1.0, 100.0 1.0, 100.0 0.0"

    expected_tssp1 = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=str(GEO.hasGeometry)),
        object=Var(value="geom_bnode"),
    )
    expected_tssp2 = TriplesSameSubjectPath.from_spo(
        subject=Var(value="geom_bnode"),
        predicate=IRI(value=str(GEO.asWKT)),
        object=Var(value="geom_var"),
    )
    expected_tssp3 = TriplesSameSubjectPath.from_spo(
        subject=Var(value="focus_node"),
        predicate=IRI(value=str(GEO.sfWithin)),
        object=RDFLiteral(value=expected_wkt, datatype=IRI(value=str(GEO.wktLiteral))),
    )
    expected_tssp_list = [expected_tssp1, expected_tssp2, expected_tssp3]
    for tssp in parser.tssp_list:
        assert tssp in expected_tssp_list

    assert not parser.tssp_list


def test_cql_spatial_graphdb_unsupported_operator():
    cql_json = {
        "op": "s_nearby",
        "args": [
            {"property": "geometry"},
            {"type": "Point", "coordinates": [150.0, -30.0]},
        ],
    }
    parser = CQLParser(cql_json=cql_json)
    with pytest.raises(NotImplementedError) as excinfo:
        parser.parse()
    assert "Operator s_nearby not implemented" in str(excinfo.value)
