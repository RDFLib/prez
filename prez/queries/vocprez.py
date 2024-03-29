from textwrap import dedent

from jinja2 import Template


def get_concept_scheme_query(iri: str, bnode_depth: int) -> str:
    query = Template(
        """
        PREFIX prez: <https://prez.dev/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        
        CONSTRUCT {  
            ?iri ?p ?o .
            
            {% if bnode_depth > 0 +%}
            ?iri ?p0 ?o0 .
            {% endif %}
            
            {% for i in range(bnode_depth) %}
            ?o{{ i }} ?p{{ i + 1 }} ?o{{ i + 1 }} .
            {% endfor %}
            
            ?iri prez:childrenCount ?childrenCount .
        }
        WHERE {
            BIND(<{{ iri }}> as ?iri)
            ?iri ?p ?o .
            FILTER (?p != skos:hasTopConcept)
            
            {
                SELECT (COUNT(?topConcept) AS ?childrenCount)
                WHERE {
                    BIND(<{{ iri }}> as ?iri)
                    ?iri skos:hasTopConcept ?topConcept .
                }
            }
            
            {% if bnode_depth > 0 %}
            ?iri ?p0 ?o0 .
            {% endif %}
            
            {% for i in range(bnode_depth) %}
            ?o{{ i }} ?p{{ i + 1 }} ?o{{ i + 1 }} .
            FILTER (isBlank(?o0))
            {% endfor %}
        }
    """
    ).render(iri=iri, bnode_depth=bnode_depth)

    return dedent(query)


def get_concept_scheme_top_concepts_query(iri: str, page: int, per_page: int) -> str:
    query = Template(
        """
        PREFIX prez: <https://prez.dev/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        
        CONSTRUCT {
            ?concept skos:prefLabel ?label .
            ?concept prez:childrenCount ?narrowerChildrenCount .
            ?iri prez:childrenCount ?childrenCount .
            ?iri skos:hasTopConcept ?concept .
            ?iri rdf:type ?type .
            ?concept rdf:type ?conceptType .
        }
        WHERE {
            BIND(<{{ iri }}> as ?iri)
            OPTIONAL {
                ?iri skos:hasTopConcept ?concept .
                ?concept skos:prefLabel ?label .
            }
            OPTIONAL {
                ?concept skos:topConceptOf ?iri .
                ?concept skos:prefLabel ?label .
            }
            ?iri rdf:type ?type .
            ?concept rdf:type ?conceptType .
        
            {
                SELECT (COUNT(?childConcept) AS ?childrenCount)
                WHERE {
                    BIND(<{{ iri }}> as ?iri)
                    ?iri skos:hasTopConcept ?childConcept .
                }
            }
        
            {
                # Using two OPTIONAL clauses with a UNION causes ?narrowConcept to be duplicated.
                # Use DISTINCT to get an accurate count.
                SELECT ?concept ?label (COUNT(DISTINCT ?narrowerConcept) AS ?narrowerChildrenCount)
                WHERE {
                    BIND(<{{ iri }}> as ?iri)
                    
                    {
                        OPTIONAL {
                            ?iri skos:hasTopConcept ?concept .
                            ?concept skos:prefLabel ?label .
                
                            OPTIONAL {
                                ?narrowerConcept skos:broader ?concept .
                            }
                            OPTIONAL {
                                ?concept skos:narrower ?narrowerConcept .
                            }
                        }
                    }
                    UNION {
                        OPTIONAL {
                            ?concept skos:topConceptOf ?iri .
                            ?concept skos:prefLabel ?label .
                
                            OPTIONAL {
                                ?narrowerConcept skos:broader ?concept .
                            }
                            OPTIONAL {
                                ?concept skos:narrower ?narrowerConcept .
                            }
                        }
                    }
                }
                GROUP BY ?concept ?label
                ORDER BY str(?label)
                LIMIT {{ limit }}
                OFFSET {{ offset }}
            }
        }
    """
    ).render(iri=iri, limit=per_page, offset=(page - 1) * per_page)

    return dedent(query)


def get_concept_narrowers_query(iri: str, page: int, per_page: int) -> str:
    query = Template(
        """
        PREFIX prez: <https://prez.dev/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        
        CONSTRUCT {
            ?concept skos:prefLabel ?label .
            ?concept prez:childrenCount ?narrowerChildrenCount .
            ?iri prez:childrenCount ?childrenCount .
            ?iri skos:narrower ?concept .
            ?iri rdf:type ?type .
            ?concept rdf:type ?conceptType .
        }
        WHERE {
            BIND(<{{ iri }}> as ?iri)
            OPTIONAL {
                ?concept skos:broader ?iri .
                ?concept skos:prefLabel ?label .
            }
            OPTIONAL {
                ?iri skos:narrower ?concept .
                ?concept skos:prefLabel ?label .
            }
            ?iri rdf:type ?type .
            
            {
                SELECT (COUNT(?childConcept) AS ?childrenCount)
                WHERE {
                    BIND(<{{ iri }}> as ?iri)
                    ?childConcept skos:broader ?iri .
                }
            }
        
            {
                SELECT ?concept ?label (skos:Concept AS ?conceptType) (COUNT(?narrowerConcept) AS ?narrowerChildrenCount)
                WHERE {
                    BIND(<{{ iri }}> as ?iri)
                    
                    {
                        OPTIONAL {
                            ?concept skos:broader ?iri .
                            ?concept skos:prefLabel ?label .
                
                            OPTIONAL {
                                ?narrowerConcept skos:broader ?concept .
                            }
                            OPTIONAL {
                                ?concept skos:narrower ?narrowerConcept .
                            }
                        }
                    }
                    UNION {
                        OPTIONAL {
                            ?iri skos:narrower ?concept .
                            ?concept skos:prefLabel ?label .
                
                            OPTIONAL {
                                ?narrowerConcept skos:broader ?concept .
                            }
                            OPTIONAL {
                                ?concept skos:narrower ?narrowerConcept .
                            }
                        }
                    }
                    
                    # Filter out any unbound ?concept rows which are invalid and may contain
                    # a count of 0. This is possible because both paths within the select
                    # query are using the OPTIONAL clause.
                    FILTER (BOUND(?concept))
                }
                GROUP BY ?concept ?label
                ORDER BY str(?label)
                LIMIT {{ limit }}
                OFFSET {{ offset }}
            }
        }
    """
    ).render(iri=iri, limit=per_page, offset=(page - 1) * per_page)

    return dedent(query)
