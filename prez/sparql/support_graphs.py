import logging

from textwrap import dedent

from prez.reference_data.prez_ns import PREZ

log = logging.getLogger(__name__)


def generate_insert_context(settings, prez: str):
    """ """
    topmost_classes = settings.top_level_classes[prez]
    collection_classes = settings.collection_classes[prez]
    member_relation = {
        "SpacePrez": "?instance_of_main_class rdfs:member ?member",
        "VocPrez": """{?instance_of_main_class ^skos:inScheme ?member }
                        UNION
      		          { ?instance_of_main_class skos:member ?member }""",
        "CatPrez": "?instance_of_main_class dcterms:hasPart ?member",
        "Profiles": "?instance_of_main_class rdfs:member ?member",
    }
    insert = dedent(
        f"""PREFIX dcat: <http://www.w3.org/ns/dcat#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX prez: <https://prez.dev/>
        PREFIX prof: <http://www.w3.org/ns/dx/prof/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        CONSTRUCT {{
                ?collectionList rdfs:member ?instance_of_top_class .
        }}
        WHERE {{
          {{
            OPTIONAL {{?instance_of_top_class a ?topmost_class
                VALUES ?topmost_class {{ {(chr(10) + 2 * chr(9)).join('<' + str(uri) + '>' for uri in topmost_classes)} }}
            }}
            }}
            BIND(
                IF(?topmost_class=prez:SpacePrezProfile, prez:SpacePrezProfileList,
                    IF(?topmost_class=prez:VocPrezProfile, prez:VocPrezProfileList,
                        IF(?topmost_class=prez:CatPrezProfile, prez:CatPrezProfileList,
                            IF(?topmost_class=prof:Profile, prez:ProfilesList,
                                IF(?topmost_class=dcat:Dataset, prez:DatasetList,
                                    IF(?topmost_class=dcat:Catalog,prez:CatalogList,
                                        IF(?topmost_class=skos:ConceptScheme,prez:SchemesList,
                                            IF(?topmost_class=skos:Collection,prez:VocPrezCollectionList,""))))))))
                                                AS ?collectionList)
                                                        }}"""
    )
    return insert
