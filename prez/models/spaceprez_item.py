from typing import Optional
from typing import Set

from pydantic import BaseConfig
from pydantic import BaseModel, root_validator
from rdflib import Namespace, URIRef, RDF
from rdflib.namespace import DCTERMS, XSD, DCAT, GEO, RDFS

from prez.services.curie_functions import get_uri_for_curie_id
from prez.sparql.methods import sparql_query_non_async

PREZ = Namespace("https://prez.dev/")

BaseConfig.arbitrary_types_allowed = True


class SpatialItem(BaseModel):
    id: Optional[str]
    uri: Optional[URIRef]
    url_path: Optional[str]
    general_class: Optional[URIRef]
    feature_curie: Optional[str]
    collection_curie: Optional[str]
    dataset_curie: Optional[str]
    parent_curie: Optional[str]
    parent_uri: Optional[URIRef]
    classes: Optional[Set[URIRef]]
    link_constructor: Optional[str]
    selected_class: Optional[URIRef] = None

    def __hash__(self):
        return hash(self.uri)

    @root_validator
    def populate(cls, values):
        dataset_curie = values.get("dataset_curie")
        collection_curie = values.get("collection_curie")
        feature_curie = values.get("feature_curie")

        def get_classes(uri):
            q = f"""
            SELECT ?class
            {{<{uri}> a ?class . }}
            """
            r = sparql_query_non_async(q, "SpacePrez")
            return frozenset([c["class"]["value"] for c in r[1]])

        if feature_curie:
            values["id"] = feature_curie
            values["uri"] = get_uri_for_curie_id(feature_curie)
            values["general_class"] = GEO.Feature
            values["parent_uri"] = get_uri_for_curie_id(collection_curie)
            values["parent_curie"] = collection_curie
        elif collection_curie:
            values["id"] = collection_curie
            values["uri"] = get_uri_for_curie_id(collection_curie)
            values["general_class"] = GEO.FeatureCollection
            values["parent_uri"] = get_uri_for_curie_id(dataset_curie)
            values["parent_curie"] = dataset_curie
            values[
                "link_constructor"
            ] = f"/s/datasets/{dataset_curie}/collections/{collection_curie}/items"
        elif dataset_curie:
            values["id"] = dataset_curie
            values["uri"] = get_uri_for_curie_id(dataset_curie)
            values["general_class"] = DCAT.Dataset
            values["link_constructor"] = f"/s/datasets/{dataset_curie}/collections"
        values["classes"] = get_classes(values["uri"])
        return values


        # uri = get_uri_for_curie_id()
        # uri = values.get("uri")
        # if uri:
        #     q = f"""
        #     PREFIX dcat: <{DCAT}>
        #     PREFIX dcterms: <{DCTERMS}>
        #     PREFIX geo: <{GEO}>
        #     PREFIX prez: <{PREZ}>
        #     PREFIX rdf: <{RDF}>
        #     PREFIX rdfs: <{RDFS}>
        #     SELECT ?item ?id ?class
        #     {{<{uri}> ^rdfs:member* ?item .
        #         {{ ?item dcterms:identifier ?id }}
        #         ?item a ?class .
        #     VALUES ?class {{geo:Feature geo:FeatureCollection dcat:Dataset}}
        #     }}"""
        #     r = sparql_query_non_async(q, "SpacePrez")
        #     if r[0] and r[1]:
        #         for res in r[1]:
        #             if res["item"]["value"] == str(uri):
        #                 values["id"] = res["id"]["value"]
        #                 values["classes"] = frozenset(
        #                     [c["class"]["value"] for c in r[1]]
        #                 )
        #             if res["class"]["value"] == str(DCAT.Dataset):
        #                 values["dataset_curie"] = res["id"]["value"]
        #                 values[
        #                     "link_constructor"
        #                 ] = f"/s/datasets/{values['dataset_curie']}/collections"
        #             elif res["class"]["value"] == str(GEO.FeatureCollection):
        #                 values["collection_curie"] = res["id"]["value"]
        #                 f"/s/datasets/{values['dataset_curie']}/collections/{values['collection_curie']}/items"
        #             elif res["class"]["value"] == str(GEO.Feature):
        #                 values["feature_curie"] = res["id"]["value"]
        #     else:
        #         raise ValueError(
        #             f"Could not find a class for {uri}, or URI does not exist in SpacePrez"
        #         )
        #     return values
        # elif dataset_curie:
        #     q = f"""
        #         PREFIX dcat: <{DCAT}>
        #         PREFIX dcterms: <{DCTERMS}>
        #         PREFIX geo: <{GEO}>
        #         PREFIX prez: <{PREZ}>
        #         PREFIX rdfs: <{RDFS}>
        #         PREFIX xsd: <{XSD}>
        #
        #         SELECT ?f ?fc ?d ?f_class ?fc_class ?d_class {{
        #             ?d dcterms:identifier "{dataset_curie}"^^prez:slug ;
        #                     a dcat:Dataset ;
        #                     a ?d_class .
        #             {f'''?fc dcterms:identifier "{collection_curie}"^^prez:slug ;
        #                     a geo:FeatureCollection ;
        #                     a ?fc_class .
        #                 ?d rdfs:member ?fc .''' if collection_curie else ""}
        #             {f'''?f dcterms:identifier "{feature_curie}"^^prez:slug ;
        #                     a geo:Feature ;
        #                     a ?f_class .
        #                 ?fc rdfs:member ?f .''' if feature_curie else ""}
        #         }}
        #         """
        #     r = sparql_query_non_async(q, "SpacePrez")
        #     if r[0]:
        #         # set the uri of the item
        #         f = r[1][0].get("f")
        #         fc = r[1][0].get("fc")
        #         d = r[1][0].get("d")
        #         if f:
        #             values["id"] = feature_curie
        #             values["uri"] = URIRef(f["value"])
        #             values["general_class"] = GEO.Feature
        #             values["parent_uri"] = URIRef(fc["value"])
        #             values["parent_curie"] = collection_curie
        #             values["classes"] = frozenset([c["f_class"]["value"] for c in r[1]])
        #         elif fc:
        #             values["id"] = collection_curie
        #             values["uri"] = URIRef(fc["value"])
        #             values["general_class"] = GEO.FeatureCollection
        #             values["parent_uri"] = URIRef(d["value"])
        #             values["parent_curie"] = dataset_curie
        #             values[
        #                 "link_constructor"
        #             ] = f"/s/datasets/{dataset_curie}/collections/{collection_curie}/items"
        #             values["classes"] = frozenset(
        #                 [c["fc_class"]["value"] for c in r[1]]
        #             )
        #         else:
        #             values["id"] = dataset_curie
        #             values["uri"] = URIRef(d["value"])
        #             values["general_class"] = DCAT.Dataset
        #             values["link_constructor"] = f"/s/datasets/{dataset_curie}/collections"
        #             values["classes"] = frozenset([c["d_class"]["value"] for c in r[1]])
