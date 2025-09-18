def test_issue_418(monkeypatch):
    """
    https://github.com/RDFLib/prez/issues/418
    CQL shacl defined queryable variable separation and non generation of correct union groupings with ggps
    """
    from prez.services.query_generation.cql import CQLParser
    from rdflib import Graph

    # Mock the queryable properties to simulate SHACL queryable
    mock_queryable_props = {
        "nsl-name-usage": "https://prez/queryables/TaxonNameUsageQueryable",
        "nsl-name-id": "https://prez/queryables/TaxonNameIDQueryable",
    }

    # Mock the system graph with SHACL shape
    mock_system_graph = Graph()
    mock_system_graph.parse(
        data="""
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix cql: <http://www.opengis.net/doc/IS/cql2/1.0/> .
        @prefix dwc: <http://rs.tdwg.org/dwc/terms/> .
        @prefix dwciri: <http://rs.tdwg.org/dwc/iri/> .
        @prefix dcterms: <http://purl.org/dc/terms/> .
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix prezqueryables: <https://prez/queryables/> .
        @prefix bore: <https://linked.data.gov.au/def/bore/> .

      prezqueryables:TaxonNameUsageQueryable a cql:Queryable ;
        a sh:PropertyShape ;
        sh:path ( dwciri:toTaxon [ sh:alternativePath ( dwc:acceptedNameUsageID dwc:parentNameUsageID ) ] ) ;
        sh:name "NSL TaxonNameUsage URI" ;
        dcterms:identifier "nsl-name-usage" ;
        sh:description "For efficient filtering based on known (full) NSL TaxonNameUsage Identifier URI" ;
        sh:datatype xsd:string ;
      .
    
      prezqueryables:TaxonNameIDQueryable a cql:Queryable ;
        a sh:PropertyShape ;
        sh:path ( dwciri:toTaxon dwc:scientificNameID ) ;
        sh:name "NSL Scientific Name ID URI" ;
        dcterms:identifier "nsl-name-id" ;
        sh:description "For efficient filtering based on known (full) NSL Name Identifier URI" ;
        sh:datatype xsd:string ;
  .
    """,
        format="turtle",
    )

    # Add the mock data to the actual system graph
    from prez.cache import prez_system_graph

    prez_system_graph += mock_system_graph

    cql_json_data = {
        "op": "or",
        "args": [
            {
                "op": "in",
                "args": [
                    {"property": "nsl-name-id"},
                    ["https://id.biodiversity.org.au/name/apni/223339"],
                ],
            },
            {
                "op": "in",
                "args": [
                    {"property": "nsl-name-usage"},
                    ["https://id.biodiversity.org.au/instance/apni/651608"],
                ],
            },
        ],
    }

    # Create parser with mock queryable properties
    parser = CQLParser(cql_json=cql_json_data, queryable_props=mock_queryable_props)
    parser.parse()

    # Get the generated SPARQL query
    query_str = parser.query_str
    print(f"Generated SPARQL query:\n{query_str}")

    # Ensure path variables are present
    path_vars = {
        var.value
        for var in parser.inner_select_vars
        if var.value.startswith("path_node_")
    }
    assert len(path_vars) >= 1, "At least one path variable should be present"

    # Ensure both identifier URIs are present in the query
    assert "https://id.biodiversity.org.au/name/apni/223339" in query_str
    assert "https://id.biodiversity.org.au/instance/apni/651608" in query_str

    # Verify UNION structure is present
    assert "UNION" in query_str
