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
        }} LIMIT {per_page} OFFSET {(page - 1) * per_page}
    """
    r = await sparql_query(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def count_datasets():
    q = f"""
        PREFIX skos: <{SKOS}>
        SELECT (COUNT(?coll) as ?count)
        WHERE {{ ?coll a skos:Collection . }}
    """
    r = await sparql_query(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def list_datasets(page: int, per_page: int):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        SELECT ?coll ?id ?label
        WHERE {{
            ?coll a skos:Collection ;
                dcterms:identifier ?id ;
                dcterms:title ?label .
            OPTIONAL {{
                ?coll dcterms:description ?desc .
            }}
            FILTER(lang(?label) = "" || lang(?label) = "en" || lang(?label) = "en-AU")
        }} LIMIT {per_page} OFFSET {(page - 1) * per_page}
    """
    r = await sparql_query(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


def query_by_graph(query: str, graph: str, include_inferencing: bool):
    """Conditionally wraps query with a GRAPH statement if inferencing is disabled"""
    if include_inferencing:
        return query
    else:
        return f"""
            GRAPH {graph} {{
                {query}
            }}
        """


async def get_catalog_construct1(
    catalog_id: Optional[str] = None,
    catalog_uri: Optional[str] = None,
    include_inferencing: bool = True,
):
    if catalog_id is None and catalog_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        ?cs dcterms:identifier ?cs_id ;
            a dcat:Catalog .
        FILTER (STR(?cs_id) = "{catalog_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{catalog_uri}> as ?cs)
        ?cs a dcat:Catalog .
    """
    # data which may contain inferencing
    query_in_graph = f"""
        ?cs ?p1 ?o1 .
    """

    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        CONSTRUCT {{
            ?cs ?p1 ?o1 .
            {construct_all_prop_obj_info}
        }}
        WHERE {{
            {query_by_id if catalog_id is not None else query_by_uri}
            {query_by_graph(query_in_graph, "?cs", include_inferencing)}
            {get_all_prop_obj_info}
        }}
    """
    r = await sparql_construct(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def get_catalog_construct2(
    catalog_id: Optional[str] = None,
    catalog_uri: Optional[str] = None,
    include_inferencing: bool = True,
):
    if catalog_id is None and catalog_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        ?c dcterms:identifier ?c_id ;
            a dcat:Catalog .
        FILTER (STR(?c_id) = "{catalog_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{catalog_uri}> as ?c)
        ?c a dcat:Catalog .
    """
    # data which may contain inferencing
    query_in_graph = f"""
        ?c skos:inScheme ?c ;
            a skos:Concept ;
            dcterms:identifier ?c_id ;
            ?label_pred ?c_label .
        FILTER(lang(?c_label) = "" || lang(?c_label) = "en")
        FILTER (?label_pred IN (dcterms:title, dcterms:title, rdfs:label))
        OPTIONAL {{
            ?c skos:broader ?broader .
        }}
        OPTIONAL {{
            ?c skos:narrower ?narrower .
        }}
    """

    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        CONSTRUCT {{
            ?c skos:inScheme ?c ;
                a skos:Concept ;
                dcterms:identifier ?c_id ;
                ?label_pred ?c_label ;
                skos:broader ?broader ;
                skos:narrower ?narrower .
        }}
        WHERE {{
            {query_by_id if catalog_id is not None else query_by_uri}
            {query_by_graph(query_in_graph, "?c", include_inferencing)}
        }}
    """
    r = await sparql_construct(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def get_concept_construct(
    concept_id: Optional[str] = None,
    catalog_id: Optional[str] = None,
    concept_uri: Optional[str] = None,
    include_inferencing: bool = True,
):
    if concept_uri is None:
        if concept_id is None or catalog_id is None:
            raise ValueError(
                "Either a Concept Scheme ID and a Concept ID or a Concept URI must be provided for a SPARQL query"
            )

    # when querying by ID via regular URL path
    query_by_id = f"""
        ?c dcterms:identifier "{catalog_id}"^^xsd:token .

        ?c dcterms:identifier "{concept_id}"^^xsd:token ;
            skos:inScheme ?c .
        """

    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{concept_uri}> as ?c)
        ?c skos:inScheme ?c .
        """

    # data which may contain inferencing
    query_in_graph = f"""
        ?c ?p1 ?o1 .
        ?c a dcat:Catalog ;
            dcterms:identifier ?c_id ;
            dcterms:title ?c_label .
        OPTIONAL {{
            ?c skos:broader ?broader .
            ?broader a skos:Concept ;
                dcterms:title ?broader_label ;
                dcterms:identifier ?broader_id ;
                skos:inScheme ?broader_cs .
            ?broader_cs a dcat:Catalog ;
                dcterms:identifier ?c_broader_id .
        }}
        OPTIONAL {{
            ?c skos:narrower ?narrower .
            ?narrower a skos:Concept ;
                dcterms:title ?narrower_label ;
                dcterms:identifier ?narrower_id ;
                skos:inScheme ?narrower_cs .
            ?narrower_cs a dcat:Catalog ;
                dcterms:identifier ?c_narrower_id .
        }}
    """

    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        PREFIX xsd: <{XSD}>

        CONSTRUCT {{
            ?c ?p1 ?o1 ;
                skos:broader ?broader ;
                skos:narrower ?narrower .
            ?broader a skos:Concept ;
                dcterms:title ?broader_label ;
                dcterms:identifier ?broader_id ;
                skos:inScheme ?broader_cs .
            ?broader_cs a dcat:Catalog ;
                dcterms:identifier ?c_broader_id .
            ?narrower a skos:Concept ;
                dcterms:title ?narrower_label ;
                dcterms:identifier ?narrower_id ;
                skos:inScheme ?narrower_cs .
            ?narrower_cs a dcat:Catalog ;
                dcterms:identifier ?c_narrower_id .
            {construct_all_prop_obj_info}

            ?c a dcat:Catalog ;
                dcterms:identifier ?c_id ;
                dcterms:title ?c_label .
        }}
        WHERE {{
            {query_by_id if concept_id is not None and catalog_id is not None else query_by_uri}
            {query_by_graph(query_in_graph, "?c", include_inferencing)}
            {get_all_prop_obj_info}
        }}
    """
    r = await sparql_construct(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def get_catalog_construct(catalog_id=None, catalog_uri=None):
    if catalog_uri is not None:
        s = f"<{catalog_uri}> dcterms:identifier ?id ;"
        p = f"<{catalog_uri}> ?p ?o ."
        b = f"BIND (<{catalog_uri}> AS ?uri)"
    elif catalog_id is not None:
        s = f'?uri dcterms:identifier "{catalog_id}"^^xsd:token ;'
        p = "?uri ?p ?o ."
        b = f'BIND ("{catalog_id}" AS ?id)'
    else:
        raise Exception("Either catalog_id or catalog_uri must be set")

    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        PREFIX rdfs: <{RDFS}>
        
        CONSTRUCT {{
            ?uri ?p ?o .
            ?p rdfs:label ?p_label .
            ?p dcterms:description ?p_comment .
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
            
            OPTIONAL {{
                ?p rdfs:label|dcterms:title ?p_label .
            }}
            
            OPTIONAL {{
                ?p rdfs:comment|dcterms:description|skos:definition ?p_comment .
            }}            
            
            {b}
        }}
    """
    print(q)
    r = await sparql_construct(q, "CatPrez")
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


def get_concept_and_scheme_uri(
    scheme_id: str = None,
    concept_id: str = None,
    concept_uri: URIRef = None,
):
    if concept_uri is not None:
        r = sparql_query_non_async(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX xsd: <{XSD}>
            SELECT ?concept_id scheme_id
            {{ <{concept_uri}> dcterms:identifier ?concept_id^^xsd:token ;
                    a skos:Concept ;
                    skos:inScheme / dcterms:identifier ?scheme_id .
            OPTIONAL {{ }}
            }} """,
            "CatPrez",
        )
        if r[0]:
            concept_id = r[1][0].get("concept_id")["value"]
            scheme_id = r[1][0].get("scheme_id")["value"]
    elif concept_id is not None:
        r = sparql_query_non_async(
            f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX xsd: <{XSD}>
            PREFIX skos: <{SKOS}>
            SELECT ?uri
            {{ ?uri dcterms:identifier "{concept_id}"^^xsd:token ;
                    a skos:Concept ;
                    skos:inScheme / dcterms:identifier "{scheme_id}"^^xsd:token .
                    }} """,
            "CatPrez",
        )
        if r[0]:
            concept_uri = r[1][0].get("uri")["value"]
    return scheme_id, concept_id, concept_uri


async def get_collection_construct1(
    collection_id: Optional[str] = None,
    collection_uri: Optional[str] = None,
    include_inferencing: bool = True,
):
    if collection_id is None and collection_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        ?coll dcterms:identifier ?coll_id ;
            a skos:Collection .
        FILTER (STR(?coll_id) = "{collection_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{collection_uri}> as ?coll)
        ?coll a skos:Collection .
    """
    # data which may contain inferencing
    query_in_graph = f"""
        ?coll ?p1 ?o1 .
    """

    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        CONSTRUCT {{
            ?coll ?p1 ?o1 .
            {construct_all_prop_obj_info}
        }}
        WHERE {{
            {query_by_id if collection_id is not None else query_by_uri}
            {query_in_graph}
            {get_all_prop_obj_info}
        }}
    """
    r = await sparql_construct(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def get_collection_construct2(
    collection_id: Optional[str] = None,
    collection_uri: Optional[str] = None,
    include_inferencing: bool = True,
):
    if collection_id is None and collection_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        ?coll dcterms:identifier ?coll_id ;
            a skos:Collection .
        FILTER (STR(?coll_id) = "{collection_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{collection_uri}> as ?coll)
        ?coll a skos:Collection .
    """
    # data which may contain inferencing
    query_in_graph = f"""
        ?coll skos:member ?c .
        ?c skos:inScheme ?c ;
            a skos:Concept ;
            dcterms:identifier ?c_id ;
            ?label_pred ?c_label .
        FILTER (?label_pred IN (dcterms:title, rdfs:label))
        ?c a dcat:Catalog ;
            dcterms:identifier ?c_id .
    """

    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        CONSTRUCT {{
            ?c skos:inScheme ?c ;
                a skos:Concept ;
                dcterms:identifier ?c_id ;
                ?label_pred ?c_label .

            ?c a dcat:Catalog ;
                dcterms:identifier ?c_id .
        }}
        WHERE {{
            {query_by_id if collection_id is not None else query_by_uri}
            {query_in_graph}
        }}
    """
    r = await sparql_construct(q, "CatPrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")
