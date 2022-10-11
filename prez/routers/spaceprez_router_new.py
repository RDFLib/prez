import io
import json
from urllib.parse import quote_plus

from connegp import RDF_MEDIATYPES
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from rdflib import Namespace, URIRef

from config import ENABLED_PREZS, SPACEPREZ_SPARQL_ENDPOINT
from prez.services.spaceprez_service import get_object_uri_and_classes, sparql_construct
from prez.services.sparql_new import generate_construct, get_labels

PREZ = Namespace("https://surroundaustralia.com/prez/")

router = APIRouter(tags=["SpacePrez"] if len(ENABLED_PREZS) > 1 else [])


@router.get("/dataset-new/{dataset_id}", summary="Get Dataset")
@router.get(
    "/dataset-new/{dataset_id}/collections-new/{collection_id}",
    summary="Get Feature Collection",
)
@router.get(
    "/dataset-new/{dataset_id}/collections-new/{collection_id}/feature-new/{feature_id}",
    summary="Get Feature",
)
async def feature_endpoint(request: Request):
    (
        _,
        _,
        _,
        feature_uri,
        collection_uri,
        dataset_uri,
        classes,
    ) = get_object_uri_and_classes(**request.path_params)
    object_uri = (
        feature_uri
        if feature_uri
        else collection_uri
        if collection_uri
        else dataset_uri
    )
    profile, mediatype = connegp_placeholder(request, classes)
    query = generate_construct(object_uri, profile)  # profile will go here in future
    _, object_graph = await sparql_construct(query, "SpacePrez")
    if mediatype in RDF_MEDIATYPES:
        return RedirectResponse(
            url=SPACEPREZ_SPARQL_ENDPOINT + "?query=" + quote_plus(query),
            headers=request.headers,
        )
    elif mediatype == "text/html":
        labels_graph = await get_labels(object_graph)

        obj = io.BytesIO(
            (object_graph + labels_graph).serialize(format="json-ld", encoding="utf-8")
        )
        return StreamingResponse(content=obj, media_type="application/ld+json")

        # return JSONResponse(content=json.loads((object_graph + labels_graph).serialize(format="json-ld")),
        #                     media_type="application/ld+json",
        #                     )


def connegp_placeholder(request, classes):
    """placeholder function for connegp"""
    return (
        URIRef("http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30"),
        "text/html",
    )
