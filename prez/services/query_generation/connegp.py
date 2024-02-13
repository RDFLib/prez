import logging
from textwrap import dedent
from typing import List, Tuple

from rdflib import URIRef, Namespace

from prez.services.curie_functions import get_uri_for_curie_id

log = logging.getLogger(__name__)

ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")
PREZ = Namespace("https://prez.dev/")


def select_profile_mediatype(
        classes: List[URIRef],
        requested_profile_uri: URIRef = None,
        requested_profile_token: str = None,
        requested_mediatypes: List[Tuple] = None,
        listing: bool = False,
):
    """
    Returns a SPARQL SELECT query which will determine the profile and mediatype to return based on user requests,
    defaults, and the availability of these in profiles.

    NB: Most specific class refers to the rdfs:Class of an object which has the most specific rdfs:subClassOf links to
    the base class delivered by that API endpoint. The base classes delivered by each API endpoint are:

    SpacePrez:
    /s/catalogs -> prez:DatasetList
    /s/catalogs/{ds_id} -> dcat:Dataset
    /s/catalogs/{ds_id}/collections/{fc_id} -> geo:FeatureCollection
    /s/catalogs/{ds_id}/collections -> prez:FeatureCollectionList
    /s/catalogs/{ds_id}/collections/{fc_id}/features -> geo:Feature

    VocPrez:
    /v/schemes -> skos:ConceptScheme
    /v/collections -> skos:Collection
    /v/schemes/{cs_id}/concepts -> skos:Concept

    CatPrez:
    /c/catalogs -> dcat:Catalog
    /c/catalogs/{cat_id}/datasets -> dcat:Dataset

    The following logic is used to determine the profile and mediatype to be returned:

    1. If a profile and mediatype are requested, they are returned if a matching profile which has the requested
    mediatype is found, otherwise the default profile for the most specific class is returned, with its default
    mediatype.
    2. If a profile only is requested, if it can be found it is returned, otherwise the default profile for the most
    specific class is returned. In both cases the default mediatype is returned.
    3. If a mediatype only is requested, the default profile for the most specific class is returned, and if the
    requested mediatype is available for that profile, it is returned, otherwise the default mediatype for that profile
    is returned.
    4. If neither a profile nor mediatype is requested, the default profile for the most specific class is returned,
    with the default mediatype for that profile.
    """
    if listing:
        profile_class = PREZ.ListingProfile
    else:
        profile_class = PREZ.ObjectProfile
    if requested_profile_token:
        requested_profile_uri = get_uri_for_curie_id(requested_profile_token)
    query = dedent(
        f"""    PREFIX altr-ext: <http://www.w3.org/ns/dx/conneg/altr-ext#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX geo: <http://www.opengis.net/ont/geosparql#>
    PREFIX prez: <https://prez.dev/>
    PREFIX prof: <http://www.w3.org/ns/dx/prof/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>

    SELECT ?profile ?title ?class (count(?mid) as ?distance) ?req_profile ?def_profile ?format ?req_format ?def_format

    WHERE {{
      VALUES ?class {{{" ".join('<' + str(klass) + '>' for klass in classes)}}}
      ?class rdfs:subClassOf* ?mid .
      ?mid rdfs:subClassOf* ?base_class .
      VALUES ?base_class {{ dcat:Dataset geo:FeatureCollection geo:Feature
      skos:ConceptScheme skos:Concept skos:Collection 
      dcat:Catalog dcat:Resource prof:Profile prez:SPARQLQuery 
      prez:SearchResult prez:CQLObjectList prez:QueryablesList prez:Object }}
      ?profile altr-ext:constrainsClass ?class ;
               altr-ext:hasResourceFormat ?format ;
               dcterms:title ?title .\
      {f'?profile a {profile_class.n3()} .'}
      {f'BIND(?profile=<{requested_profile_uri}> as ?req_profile)' if requested_profile_uri else ''}
      BIND(EXISTS {{ ?shape sh:targetClass ?class ;
                           altr-ext:hasDefaultProfile ?profile }} AS ?def_profile)
      {generate_mediatype_if_statements(requested_mediatypes) if requested_mediatypes else ''}
      BIND(EXISTS {{ ?profile altr-ext:hasDefaultResourceFormat ?format }} AS ?def_format)
    }}
    GROUP BY ?class ?profile ?req_profile ?def_profile ?format ?req_format ?def_format ?title
    ORDER BY DESC(?req_profile) DESC(?distance) DESC(?def_profile) DESC(?req_format) DESC(?def_format)"""
    )
    return query


def generate_mediatype_if_statements(requested_mediatypes: list):
    """
    Generates a list of if statements which will be used to determine the mediatype to return based on user requests,
    and the availability of these in profiles.
    These are of the form:
      BIND(
        IF(?format="application/ld+json", "0.9",
          IF(?format="text/html", "0.8",
            IF(?format="image/apng", "0.7", ""))) AS ?req_format)
    """
    # TODO ConnegP appears to return a tuple of q values and profiles for headers, and only profiles (no q values) if they
    # are not specified in QSAs.
    if not isinstance(next(iter(requested_mediatypes)), tuple):
        requested_mediatypes = [(1, mt) for mt in requested_mediatypes]

    line_join = "," + "\n"
    ifs = (
        f"BIND(\n"
        f"""{line_join.join({chr(9) + 'IF(?format="' + tup[1] + '", "' + str(tup[0]) + '"' for tup in requested_mediatypes})}"""
        f""", ""{')' * len(requested_mediatypes)}\n"""
        f"\tAS ?req_format)"
    )
    return ifs
