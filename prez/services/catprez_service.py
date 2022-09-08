from typing import Optional

from prez.services.sparql_utils import *


async def count_catalogs():
    q = f"""
        PREFIX dcat: <{DCAT}>
        SELECT (COUNT(?c) as ?count)
        WHERE {{
            ?c a dcat:Catalog .
        }}
    """
    r = await sparql_query(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def list_catalogs(page: int, per_page: int):
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        SELECT ?c ?id ?label
        WHERE {{
            ?c a dcat:Catalog ;
                dcterms:identifier ?id ;
                dcterms:title ?label .                
            OPTIONAL {{
                ?c dcterms:description ?desc .
            }}        
            
            FILTER (?c != <https://example.com/prez/catprez>)
        }} LIMIT {per_page} OFFSET {(page - 1) * per_page}
    """
    r = await sparql_query(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


def get_catalog_uri(
    id: str = None,
    uri: URIRef = None,
):
    if uri is not None:
        r = sparql_query_non_async(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX xsd: <{XSD}>
            SELECT ?uri ?id
            {{ <{uri}> dcterms:identifier ?id^^xsd:token .
            OPTIONAL {{ }}
            }} """,
            "CatPrez",
        )
        if r[0]:
            id = r[1][0].get("id")["value"]
    elif id is not None:
        r = sparql_query_non_async(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX xsd: <{XSD}>
            PREFIX skos: <{SKOS}>
            SELECT ?uri ?id ?concept
            {{ ?uri dcterms:identifier "{id}"^^xsd:token ;
                    a dcat:Catalog
                    }} """,
            "CatPrez",
        )
        if r[0]:
            uri = r[1][0].get("uri")["value"]
    return id, uri


def get_resource_uri(
    id: str = None,
    uri: URIRef = None,
):
    if uri is not None:
        r = sparql_query_non_async(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX xsd: <{XSD}>
            SELECT ?uri ?id
            WHERE {{ 
                <{uri}> dcterms:identifier ?id^^xsd:token .
                BIND (<{uri}> AS ?uri)
            }}
            """,
            "CatPrez",
        )
        if r[0]:
            id = r[1][0].get("id")["value"]
    elif id is not None:
        r = sparql_query_non_async(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX xsd: <{XSD}>
            PREFIX skos: <{SKOS}>
            SELECT ?uri ?id
            WHERE {{ 
                ?uri dcterms:identifier "{id}"^^xsd:token .
                BIND ("{id}" AS ?id)
            }}
            """,
            "CatPrez",
        )
        if r[0]:
            uri = r[1][0].get("uri")["value"]
    return id, uri


async def get_catprez_home_construct():
    q = """
        PREFIX dcat: <http://www.w3.org/ns/dcat#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        
        CONSTRUCT {
            ?c a dcat:Dataset ;
                dcterms:identifier "catprez"^^xsd:token ;
                dcterms:title ?title ;
                dcterms:description ?desc ;
                dcterms:hasPart ?part ;
            .
            ?part
                dcterms:identifier ?part_id ;
                rdfs:label ?part_title ;
            .
            ?p
                rdfs:label ?p_label ;
                rdfs:comment ?p_comment ;
            .
        }
        WHERE {
            ?c a dcat:Catalog ;
                dcterms:identifier "catprez"^^xsd:token ;
                dcterms:title ?title ;
                dcterms:description ?desc ;
            .
          
            ?part a dcat:Catalog ;
                dcterms:identifier ?part_id ;
                dcterms:title ?part_title ;
            .
          
            VALUES ?p { dcterms:identifier dcterms:title dcterms:description dcterms:hasPart }
            OPTIONAL {
                ?p rdfs:label ?p_label .
            } 
            OPTIONAL {
                ?p rdfs:comment ?p_comment .
            }  
          
            FILTER (?part_id != "catprez"^^xsd:string )          
        }
        """
    r = await sparql_construct(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def get_catalog_construct(catalog_id=None, catalog_uri=None):
    if catalog_uri is not None:
        s = f"<{catalog_uri}> dcterms:identifier ?id ;"
        p = f"<{catalog_uri}> ?p ?o .\n<{catalog_uri}> dcterms:hasPart ?part .\n<{catalog_uri}> prov:qualifiedAttribution ?qa ."
        b = f"BIND (<{catalog_uri}> AS ?uri)"
    elif catalog_id is not None:
        s = f'?uri dcterms:identifier "{catalog_id}"^^xsd:token ;'
        p = "?uri ?p ?o .\n?url dcterms:hasPart ?part .\n?url prov:qualifiedAttribution ?qa ."
        b = ""
    else:
        raise Exception("Either catalog_id or catalog_uri must be set")

    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX prov: <{PROV}>
        PREFIX skos: <{SKOS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX xsd: <{XSD}>

        CONSTRUCT {{
            ?uri ?p ?o .
            ?p 
                rdfs:label ?p_label ;
                dcterms:description ?p_comment ;
            .
            ?o 
                rdfs:label ?o_label ;
                dcterms:description ?o_comment ;
            .
            ?part 
                rdfs:label ?part_title ;
                dcterms:identifier ?part_id ;
            .
            ?o ?p2 ?o2 .
            ?p2 rdfs:label ?p2_label ;
                dcterms:description ?p2_comment .
            ?o2 rdfs:label ?o2_label ;
                dcterms:description ?o2_comment .
        }}
        WHERE {{
            {{
                {s}
                    a dcat:Catalog ;
                .
            }}
            {{
                {p}
            }}
            ?part 
                dcterms:title ?part_title ;
                dcterms:identifier ?part_id ;
            .

            OPTIONAL {{
                ?p rdfs:label|dcterms:title|skos:prefLabel ?p_label .
            }}

            OPTIONAL {{
                ?p rdfs:comment|dcterms:description|skos:definition ?p_comment .
            }}                    

            OPTIONAL {{
                ?o rdfs:label|dcterms:title|skos:prefLabel ?o_label .
            }}

            OPTIONAL {{
                ?o rdfs:comment|dcterms:description|skos:definition ?o_comment .
            }} 

            OPTIONAL {{
                ?o ?p2 ?o2 .
                FILTER(ISBLANK(?o))

                OPTIONAL {{
                    ?p2 rdfs:label|dcterms:title|skos:prefLabel ?p2_label .
                }}

                OPTIONAL {{
                    ?p2 rdfs:comment|dcterms:description|skos:definition ?p2_comment .
                }}

                OPTIONAL {{
                    ?o2 rdfs:label|dcterms:title|skos:prefLabel ?o2_label .
                }}

                OPTIONAL {{
                    ?o2 rdfs:comment|dcterms:description|skos:definition ?o2_comment .
                }}
            }}

            {b}
        }}
    """
    r = await sparql_construct(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def get_resource_construct(resource_id=None, resource_uri=None):
    if resource_uri is not None:
        s = f"<{resource_uri}> dcterms:identifier ?id ;"
        p = f"<{resource_uri}> ?p ?o ."
        b = f"BIND (<{resource_uri}> AS ?uri)"
    elif resource_id is not None:
        s = f'?uri dcterms:identifier "{resource_id}"^^xsd:token ;'
        p = "?uri ?p ?o ."
        b = ""
    else:
        raise Exception("Either resource_id or resource_uri must be set")

    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX prov: <{PROV}>
        PREFIX skos: <{SKOS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX xsd: <{XSD}>

        CONSTRUCT {{
            ?uri ?p ?o .
            ?p 
                rdfs:label ?p_label ;
                dcterms:description ?p_comment ;
            .
            ?o 
                rdfs:label ?o_label ;
                dcterms:description ?o_comment ;
            .
            ?o ?p2 ?o2 .
            ?p2 rdfs:label ?p2_label ;
                dcterms:description ?p2_comment .
            ?o2 rdfs:label ?o2_label ;
                dcterms:description ?o2_comment .
        }}
        WHERE {{
            VALUES ?type {{ dcat:Resource dcat:Dataset }}
            {{
                {s} a ?type .
            }}
            {{
                {p}
            }}

            OPTIONAL {{
                ?p rdfs:label|dcterms:title|skos:prefLabel ?p_label .
            }}

            OPTIONAL {{
                ?p rdfs:comment|dcterms:description|skos:definition ?p_comment .
            }}                    

            OPTIONAL {{
                ?o rdfs:label|dcterms:title|skos:prefLabel ?o_label .
            }}

            OPTIONAL {{
                ?o rdfs:comment|dcterms:description|skos:definition ?o_comment .
            }} 

            OPTIONAL {{
                ?o ?p2 ?o2 .
                FILTER(ISBLANK(?o))

                OPTIONAL {{
                    ?p2 rdfs:label|dcterms:title|skos:prefLabel ?p2_label .
                }}

                OPTIONAL {{
                    ?p2 rdfs:comment|dcterms:description|skos:definition ?p2_comment .
                }}

                OPTIONAL {{
                    ?o2 rdfs:label|dcterms:title|skos:prefLabel ?o2_label .
                }}

                OPTIONAL {{
                    ?o2 rdfs:comment|dcterms:description|skos:definition ?o2_comment .
                }}
            }}

            {b}
        }}
    """
    r = await sparql_construct(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")