import io
import json
import logging
import re
import time
import urllib.parse
from urllib.parse import urlencode

from fastapi.responses import PlainTextResponse, RedirectResponse
from rdf2geojson import convert
from rdflib import RDF, URIRef, BNode
from rdflib.namespace import GEO
from sparql_grammar_pydantic import IRI, TriplesSameSubject, TriplesSameSubjectPath, Var

from prez.config import settings
from prez.enums import NonAnnotatedRDFMediaType, AnnotatedRDFMediaType
from prez.exceptions.model_exceptions import URINotFoundException
from prez.models.ogc_features import Collection, Link, Links
from prez.models.query_params import ListingQueryParams
from prez.reference_data.prez_ns import ALTREXT, ONT, PREZ
from prez.renderers.renderer import (
    create_self_alt_links,
    generate_link_headers,
    get_brisbane_timestamp,
)
from prez.renderers.renderer import return_annotated_rdf, return_from_graph
from prez.services.connegp_service import RDF_MEDIATYPES
from prez.services.curie_functions import get_curie_id_for_uri
from prez.services.link_generation import add_prez_links
from prez.services.listings import listing_function
from prez.services.query_generation.umbrella import PrezQueryConstructor

log = logging.getLogger(__name__)


async def object_function(
        data_repo, system_repo, endpoint_structure, pmts, profile_nodeshape, url, query_params
):
    if pmts.selected["profile"] == ALTREXT["alt-profile"]:
        list_query_params = ListingQueryParams(
            mediatype=pmts.selected["mediatype"],
            _filter=None,
            q=None,
            page=1,
            limit=100,
            startindex=None,
            offset=None,
            facet_profile=None,
            datetime=None,
            bbox=[],
            filter_crs=None,
            filter_lang=None,
            order_by=None,
            order_by_direction=None,
            subscription_key=query_params.subscription_key
        )
        return await listing_function(
            data_repo=data_repo,
            system_repo=system_repo,
            endpoint_structure=endpoint_structure,
            pmts=pmts,
            profile_nodeshape=profile_nodeshape,
            query_params=list_query_params,
            original_endpoint_type=ONT["ObjectEndpoint"],
            url=url,
            endpoint_nodeshape=None,
            concept_hierarchy_query=None,
            cql_parser=None,
            search_query=None,
        )
    if "anot+" in pmts.selected["mediatype"]:
        profile_nodeshape.tss_list.append(
            TriplesSameSubject.from_spo(
                subject=profile_nodeshape.focus_node,
                predicate=IRI(value="https://prez.dev/type"),
                object=IRI(value="https://prez.dev/FocusNode"),
            )
        )
    query = PrezQueryConstructor(
        profile_triples=profile_nodeshape.tssp_list,
        profile_gpnt=profile_nodeshape.gpnt_list,
        construct_tss_list=profile_nodeshape.tss_list,
    ).to_string()

    if pmts.requested_mediatypes and (
            pmts.requested_mediatypes[0][0] == "application/sparql-query"
    ):
        return PlainTextResponse(query, media_type="application/sparql-query")
    query_start_time = time.time()
    item_graph, _ = await data_repo.send_queries([query], [])
    log.debug(f"Query time: {time.time() - query_start_time}")
    if settings.prez_ui_url:
        # If HTML or no specific media type requested
        if pmts.requested_mediatypes and (
                pmts.requested_mediatypes[0][0] in ("text/html", "*/*")
        ):
            item_uri = URIRef(profile_nodeshape.focus_node.value)
            await add_prez_links(item_graph, data_repo, endpoint_structure, [item_uri])
            prez_link = item_graph.value(
                subject=item_uri, predicate=URIRef("https://prez.dev/link"), any=True
            )
            prez_ui_url = re.sub(r"/+$", "", settings.prez_ui_url)
            if prez_link:
                return RedirectResponse(prez_ui_url + str(prez_link))
            elif len(item_graph):
                return RedirectResponse(prez_ui_url + "/object?uri=" + urllib.parse.quote_plus(item_uri))
            else:
                return RedirectResponse(
                    prez_ui_url + "/404?uri=" + urllib.parse.quote_plus(item_uri)
                )
    if "anot+" in pmts.selected["mediatype"]:
        item_graph.add((BNode(), PREZ.currentProfile, pmts.selected["profile"]))
        await add_prez_links(item_graph, data_repo, endpoint_structure)
    return await return_from_graph(
        item_graph,
        pmts.selected["mediatype"],
        pmts.selected["profile"],
        pmts.generate_response_headers(),
        pmts.selected["class"],
        data_repo,
        system_repo,
        url=url,
    )


def create_parent_link(url):
    return Link(
        href=f"{settings.system_uri}{url.path.split('/items')[0]}",
        rel="collection",
        type="application/geo+json",
    )


async def ogc_features_object_function(
        template_queries,
        selected_mediatype,
        profile_nodeshape,
        url,
        data_repo,
        system_repo,
        path_params,
):
    collection_uri = path_params.get("collection_uri")
    feature_uri = path_params.get("feature_uri")
    queries = []
    if template_queries:
        if feature_uri:
            focus_uri = feature_uri
        else:
            focus_uri = collection_uri
        for query in template_queries:
            queries.append(
                query.replace(
                    "VALUES ?focusNode { UNDEF }",
                    f"VALUES ?focusNode {{ {focus_uri.n3()} }}",
                )
            )
    else:
        if feature_uri is None:  # feature collection
            collection_iri = IRI(value=collection_uri)
            construct_tss_list = None
            tssp_list = [
                TriplesSameSubjectPath.from_spo(
                    collection_iri, IRI(value=RDF.type), Var(value="type")
                )
            ]
        else:  # feature
            feature_iri = IRI(value=feature_uri)
            triples = [
                (feature_iri, Var(value="prop"), Var(value="val")),
                (
                    feature_iri,
                    IRI(value=GEO.hasGeometry),
                    Var(value="bn"),
                ),  # Pyoxigraph DESCRIBE does not follow blank nodes, so specify the geometry path
                (Var(value="bn"), IRI(value=GEO.asWKT), Var(value="wkt")),
            ]
            tssp_list = [TriplesSameSubjectPath.from_spo(*triple) for triple in triples]
            construct_tss_list = [
                TriplesSameSubject.from_spo(*triple) for triple in triples
            ]
        queries.append(
            PrezQueryConstructor(
                construct_tss_list=construct_tss_list,
                profile_triples=tssp_list,
            ).to_string()
        )

    query_start_time = time.time()
    item_graph, _ = await data_repo.send_queries(queries, [])
    log.debug(f"Query time: {time.time() - query_start_time}")

    if len(item_graph) == 0:
        uri = feature_uri if feature_uri else collection_uri
        raise URINotFoundException(uri=uri)

    annotations_graph = None
    if (selected_mediatype in AnnotatedRDFMediaType) or \
            (selected_mediatype == "application/json") or \
            (selected_mediatype == "application/geo+json" and "human" in profile_nodeshape.uri.lower()):
        annotations_graph = await return_annotated_rdf(item_graph, data_repo, system_repo)

    link_headers = None
    if selected_mediatype == "application/sparql-query":
        content = io.BytesIO("\n".join(queries).encode("utf-8"))
    elif selected_mediatype == "application/json":
        collectionId = get_curie_id_for_uri(collection_uri)
        collection = create_collection_json(
            collectionId, collection_uri, annotations_graph, url
        )
        link_headers = generate_link_headers(collection.links)
        content = io.BytesIO(
            collection.model_dump_json(exclude_none=True).encode("utf-8")
        )
    elif selected_mediatype == "application/geo+json":
        if "human" in profile_nodeshape.uri.lower():  # human readable profile
            item_graph += annotations_graph
            geojson = convert(g=item_graph, do_validate=False, iri2id=get_curie_id_for_uri, kind="human")
        else:
            geojson = convert(g=item_graph, do_validate=False, iri2id=get_curie_id_for_uri, kind="machine")
        self_alt_links = create_self_alt_links(selected_mediatype, url)
        parent_link = create_parent_link(url)
        all_links = [*self_alt_links, parent_link]
        all_links_dict = Links(links=all_links).model_dump(exclude_none=True)
        link_headers = generate_link_headers(all_links)
        geojson["links"] = all_links_dict["links"]
        geojson["timeStamp"] = get_brisbane_timestamp()
        content = io.BytesIO(json.dumps(geojson).encode("utf-8"))
    elif selected_mediatype in NonAnnotatedRDFMediaType:
        content = io.BytesIO(
            item_graph.serialize(format=selected_mediatype, encoding="utf-8")
        )
    elif selected_mediatype in AnnotatedRDFMediaType:
        item_graph += annotations_graph
        non_anot_mt = selected_mediatype.replace("anot+", "")
        content = io.BytesIO(
            item_graph.serialize(format=non_anot_mt, encoding="utf-8")
        )
    return content, link_headers


def create_collection_json(collection_curie, collection_uri, annotations_graph, url):
    return Collection(
        id=collection_curie,
        title=annotations_graph.value(
            subject=collection_uri, predicate=PREZ.label, default=None
        ),
        description=annotations_graph.value(
            subject=collection_uri, predicate=PREZ.description, default=None
        ),
        links=[
            Link(
                href=URIRef(
                    f"{settings.system_uri}{url.path}/items?{urlencode({'_mediatype': mt})}"
                ),
                rel="items",
                type=mt,
            )
            for mt in ["application/geo+json", *RDF_MEDIATYPES]
        ],
    )
