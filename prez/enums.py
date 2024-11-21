from enum import Enum


class NonAnnotatedRDFMediaType(Enum):
    LD_JSON = "application/ld+json"
    RDF_XML = "application/rdf+xml"
    TURTLE = "text/turtle"
    N_TRIPLES = "application/n-triples"


class AnnotatedRDFMediaType(Enum):
    ANOT_LD_JSON = "application/anot+ld+json"
    ANOT_RDF_XML = "application/anot+rdf+xml"
    ANOT_TURTLE = "text/anot+turtle"
    ANOT_N_TRIPLES = "application/anot+n-triples"


class SPARQLQueryMediaType(Enum):
    SPARQL_QUERY = "application/sparql-query"


class JSONMediaType(Enum):
    JSON = "application/json"


class GeoJSONMediaType(Enum):
    GEOJSON = "application/geo+json"


class OrderByDirectionEnum(Enum):
    ASC = "ASC"
    DESC = "DESC"


class FilterLangEnum(Enum):
    CQL_JSON = "cql2-json"


class SearchMethod(str, Enum):
    DEFAULT = "default"
    FTS_FUSEKI = "fts_fuseki"
