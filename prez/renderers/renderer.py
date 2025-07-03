import io
import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from aiocache import cached
from fastapi import Depends
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse
from httpx import URL
from rdf2geojson import convert
from rdf2geojson.contrib.geomet import wkt
from rdflib import Graph
from rdflib import URIRef
from rdflib.namespace import GEO, RDF
from sparql_grammar_pydantic import (
    IRI,
    Var,
)

from prez.cache import endpoints_graph_cache
from prez.cache import prefix_graph
from prez.config import settings
from prez.dependencies import get_endpoint_uri, get_system_repo, get_url
from prez.models.ogc_features import Collection, Collections, Link, Links, Queryables, Spatial, Extent
from prez.models.query_params import ListingQueryParams
from prez.reference_data.prez_ns import OGCFEAT, ONT, PREZ
from prez.renderers.csv_renderer import render_csv_dropdown
from prez.renderers.json_renderer import NotFoundError, render_json_dropdown
from prez.repositories import Repo
from prez.services.annotations import get_annotation_properties
from prez.services.connegp_service import RDF_MEDIATYPES, MINIMAL_OGC_FEATURES_RDF_FORMATS
from prez.services.connegp_service import RDF_SERIALIZER_TYPES_MAP
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.query_generation.shacl import NodeShape

log = logging.getLogger(__name__)


async def return_from_graph(
    graph,
    mediatype,
    profile,
    profile_headers,
    selected_class: URIRef,
    repo: Repo,
    system_repo: Repo,
    query_params: Optional[ListingQueryParams] = None,
    url: str = None,
):
    profile_headers["Content-Disposition"] = "inline"

    if str(mediatype) in RDF_MEDIATYPES:
        return await return_rdf(graph, mediatype, profile_headers)

    elif profile == URIRef("https://w3id.org/profile/dd"):
        annotations_graph = await return_annotated_rdf(graph, repo, system_repo)
        graph.__iadd__(annotations_graph)

        try:
            # TODO: Currently, data is generated in memory, instead of in a streaming manner.
            #       Not possible to do a streaming response yet since we are reading the RDF
            #       data into an in-memory graph.
            jsonld_data = await render_json_dropdown(graph, profile, selected_class)

            if str(mediatype) == "text/csv":
                iri = graph.value(None, RDF.type, selected_class)
                if iri:
                    filename = get_curie_id_for_uri(URIRef(str(iri)))
                else:
                    filename = selected_class.split("#")[-1].split("/")[-1]
                stream = render_csv_dropdown(jsonld_data["@graph"])
                response = StreamingResponse(stream, media_type=mediatype)
                response.headers["Content-Disposition"] = (
                    f"attachment;filename={filename}.csv"
                )
                return response

            # application/json
            stream = io.StringIO(json.dumps(jsonld_data))
            return StreamingResponse(stream, media_type=mediatype)

        except NotFoundError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(err))

    elif str(mediatype) == "application/geo+json":
        if "human" in profile.lower():
            kind = "human"
            annotations_graph = await return_annotated_rdf(graph, repo, system_repo)
            graph.__iadd__(annotations_graph)
        else:
            kind = "machine"
        collection_label = None
        if len(list(graph.subjects(RDF.type, GEO["Feature"]))) > 0:
            collection_label="FeatureCollection containing Features from listing query"
        geojson = convert(
            g=graph,
            do_validate=False,
            iri2id=get_curie_id_for_uri,
            collection_label=collection_label,
            kind=kind
        )
        count = None  # for an object; no count query.
        s_o = graph.subject_objects(
            predicate=PREZ["count"]
        )  # for a list; graph will contain a count.
        for tup in s_o:
            str_count = str(tup[1])
            count = get_geojson_int_count(str_count)
        headers, geojson = await generate_geojson_extras(
            count, geojson, query_params, "application/geo+json", url
        )
        content = io.BytesIO(json.dumps(geojson).encode("utf-8"))
        return StreamingResponse(content=content, media_type=mediatype)

    else:
        if "anot+" in mediatype:
            non_anot_mediatype = mediatype.replace("anot+", "")
            annotations_graph = await return_annotated_rdf(graph, repo, system_repo)
            graph.__iadd__(annotations_graph)
            graph.namespace_manager = prefix_graph.namespace_manager
            content = io.BytesIO(
                graph.serialize(format=non_anot_mediatype, encoding="utf-8")
            )
            return StreamingResponse(
                content=content, media_type=non_anot_mediatype, headers=profile_headers
            )

        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Unsupported mediatype: {mediatype}."
        )


def get_geojson_int_count(count_str: str):
    if count_str.startswith(">"):
        count = int(
            count_str[1:]
        )  # TODO increment maximum counts based on current page.
    else:
        count = int(count_str)
    return count


async def return_rdf(graph: Graph, mediatype, profile_headers):
    RDF_SERIALIZER_TYPES_MAP["text/anot+turtle"] = "turtle"
    obj = io.BytesIO(
        graph.serialize(
            format=RDF_SERIALIZER_TYPES_MAP[str(mediatype)], encoding="utf-8"
        )
    )
    profile_headers["Content-Disposition"] = "inline"
    return StreamingResponse(content=obj, media_type=mediatype, headers=profile_headers)


async def return_annotated_rdf(
    graph: Graph,
    repo: Repo,
    system_repo: Repo,
) -> Graph:
    t_start = time.time()
    annotations_graph = await get_annotation_properties(graph, repo, system_repo)
    # get annotations for annotations - no need to do this recursively
    annotations_graph += await get_annotation_properties(
        annotations_graph, repo, system_repo
    )
    log.debug(f"Time to get annotations: {time.time() - t_start}")
    # return graph.__iadd__(annotations_graph)
    return annotations_graph


async def generate_geojson_extras(
    count, geojson, query_params, selected_mediatype, url
):
    all_links = create_self_alt_links(selected_mediatype, url, query_params, count)
    all_links_dict = Links(links=all_links).model_dump(exclude_none=True)
    link_headers = generate_link_headers(all_links)
    geojson["links"] = all_links_dict["links"]
    geojson["timeStamp"] = get_brisbane_timestamp()
    if count:  # listing
        geojson["numberMatched"] = count
        if geojson.get("features"):
            geojson["numberReturned"] = len(geojson["features"])
        else:
            geojson["numberReturned"] = 0
    return link_headers, geojson


def create_collections_json(
    item_graph, annotations_graph, url, selected_mediatype, query_params, count: str
):
    collections_list = []
    for s, p, o in item_graph.triples((None, RDF.type, GEO.FeatureCollection)):
        extent_bnode = item_graph.value(subject=s, predicate=GEO.hasBoundingBox, default=None)
        if extent_bnode:
            extent_geom = item_graph.value(subject=extent_bnode, predicate=GEO.asWKT, default=None)
            bbox_obj = wkt.loads(str(extent_geom))
            if bbox_obj["type"] != "Polygon":
                json_extent = None
            else:
                coordinates_array = bbox_obj["coordinates"]
                coords = coordinates_array[0]
                bbox = [coords[0][0], coords[0][1], coords[2][0], coords[2][1]]
                json_extent = Extent(spatial=Spatial(bbox=[bbox]))
        else:
            json_extent = None
        curie_id = get_curie_id_for_uri(s)
        collections_list.append(
            Collection(
                id=curie_id,
                title=annotations_graph.value(
                    subject=s, predicate=PREZ.label, default=None
                ),
                description=annotations_graph.value(
                    subject=s, predicate=PREZ.description, default=None
                ),
                extent=json_extent,
                links=[
                    Link(
                        href=URIRef(
                            f"{settings.system_uri}{url.path}/{curie_id}/items?{urlencode({'_mediatype': mt})}"
                        ),
                        rel="items",
                        type=mt,
                    )
                    for mt in ["application/geo+json", *MINIMAL_OGC_FEATURES_RDF_FORMATS]
                ],
            )
        )
    self_alt_links = create_self_alt_links(selected_mediatype, url, query_params, count)
    collections = Collections(
        collections=collections_list,
        links=self_alt_links,
    )
    return collections


def create_self_alt_links(selected_mediatype, url, query_params=None, count=None):
    self_alt_links = []
    for mt in [selected_mediatype, *RDF_MEDIATYPES]:
        self_alt_links.append(
            Link(
                href=URIRef(
                    f"{settings.system_uri}{url.path}?{urlencode( dict(URL(str(url)).params) | {'_mediatype': mt} )}"
                ),
                rel="self" if mt == selected_mediatype else "alternate",
                type=mt,
                title="this document",
            )
        )
    if count:  # only for listings; add prev/next links
        page = query_params.page
        limit = query_params.limit
        if page != 1:
            prev_page = page - 1
            self_alt_links.append(
                Link(
                    href=URIRef(
                        f"{settings.system_uri}{url.path}?{urlencode({'_mediatype': selected_mediatype, 'page': prev_page, 'limit': limit})}"
                    ),
                    rel="prev",
                    type=selected_mediatype,
                    title="previous page",
                )
            )
        if count > page * limit:
            next_page = page + 1
            self_alt_links.append(
                Link(
                    href=URIRef(
                        f"{settings.system_uri}{url.path}?{urlencode({'_mediatype': selected_mediatype, 'page': next_page, 'limit': limit})}"
                    ),
                    rel="next",
                    type=selected_mediatype,
                    title="next page",
                )
            )
    return self_alt_links


def generate_link_headers(links) -> Dict[str, str]:
    link_header = ", ".join(
        [f'<{link.href}>; rel="{link.rel}"; type="{link.type}"' for link in links]
    )
    return {"Link": link_header}


async def handle_alt_profile(original_endpoint_type, pmts):
    endpoint_nodeshape_map = {
        ONT["ObjectEndpoint"]: URIRef("http://example.org/ns#AltProfilesForObject"),
        ONT["ListingEndpoint"]: URIRef("http://example.org/ns#AltProfilesForListing"),
    }
    endpoint_uri = endpoint_nodeshape_map[original_endpoint_type]
    endpoint_nodeshape = NodeShape(
        uri=endpoint_uri,
        graph=endpoints_graph_cache,
        kind="endpoint",
        focus_node=Var(value="focus_node"),
        path_nodes={
            "path_node_1": IRI(value=pmts.selected["class"])
        },  # hack - not sure how (or if) the class can be
        # 'dynamicaly' expressed in SHACL. The class is only known at runtime
    )
    return endpoint_nodeshape


def get_brisbane_timestamp():
    # Get current time in Brisbane
    brisbane_time = datetime.now(ZoneInfo("Australia/Brisbane"))

    # Format the timestamp
    timestamp = brisbane_time.strftime("%Y-%m-%dT%H:%M:%S%z")

    # Insert colon in timezone offset
    return f"{timestamp[:-2]}:{timestamp[-2:]}"


# TODO cache this
async def generate_queryables_from_shacl_definition(
    url: str = Depends(get_url),
    endpoint_uri: URIRef = Depends(get_endpoint_uri),
    system_repo: Repo = Depends(get_system_repo),
):
    query = """
    PREFIX cql: <http://www.opengis.net/doc/IS/cql2/1.0/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    CONSTRUCT {
    ?queryable cql:id ?id ;
    	cql:name ?title ;
    	cql:description ?description ;
    	cql:datatype ?type ;
    	cql:enum ?enums .
    }
    WHERE {?queryable a cql:Queryable ;
        dcterms:identifier ?id ;
        sh:name ?title ;
        sh:description ?description ;
        sh:datatype ?type .
        OPTIONAL { ?queryable sh:in/rdf:rest*/rdf:first ?enums }
    }
    """
    g, _ = await system_repo.send_queries([query], [])
    if (
        len(g) == 0
    ):  # will auto generate queryables from data - less preferable approach
        return None
    jsonld_string = g.serialize(format="json-ld")
    jsonld = json.loads(jsonld_string)
    queryable_props = {}
    for item in jsonld:
        id_value = item["http://www.opengis.net/doc/IS/cql2/1.0/id"][0]["@value"]
        queryable_props[id_value] = {
            "title": item["http://www.opengis.net/doc/IS/cql2/1.0/name"][0]["@value"],
            "type": item["http://www.opengis.net/doc/IS/cql2/1.0/datatype"][0][
                "@id"
            ].split("#")[
                -1
            ],  # hack
            "description": item["http://www.opengis.net/doc/IS/cql2/1.0/description"][
                0
            ]["@value"],
        }
        enum = item.get(
            "http://www.opengis.net/doc/IS/cql2/1.0/enum"
        )  # enums are optional.
        if enum:
            queryable_props[id_value]["enum"] = [enum_item["@id"] for enum_item in enum]
    if endpoint_uri == OGCFEAT["queryables-global"]:
        title = "Global Queryables"
        description = (
            "Global queryable properties for all collections in the OGC Features API."
        )
    else:
        title = "Local Queryables"
        description = (
            "Local queryable properties for the collection in the OGC Features API."
        )
    queryable_params = {
        "$id": f"{settings.system_uri}{url.path}",
        "title": title,
        "description": description,
        "properties": queryable_props,
    }
    return Queryables(**queryable_params)


@cached(ttl=600, key_builder=lambda *args, **kwargs: args[1])  # first arg is function; subsequent are actual args.
async def _cached_feature_collection_query(
    collection_uri, data_repo, feature_collection_query
):
    """cache the feature collection information for 10 minutes as it is an expensive query at present"""
    fc_item_graph, _ = await data_repo.send_queries([feature_collection_query], [])
    return fc_item_graph
