import io
import json
import logging
import pickle
from typing import Annotated, Optional

from aiocache import caches
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from pydantic import ValidationError
from rdflib import VANN, BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response, StreamingResponse

from prez.cache import endpoints_graph_cache, prefix_graph
from prez.config import settings
from prez.dependencies import get_runtime_settings, get_system_repo
from prez.enums import JSONMediaType, NonAnnotatedRDFMediaType
from prez.models.endpoint_config import RootModel, configure_endpoings_example
from prez.config import Settings
from prez.reference_data.prez_ns import PREZ
from prez.renderers.renderer import return_from_graph, return_rdf
from prez.repositories import Repo
from prez.services.connegp_service import RDF_MEDIATYPES, NegotiatedPMTs
from prez.services.generate_endpoint_rdf import create_endpoint_rdf
from prez.services.jena_assembler_queryables import (
    JenaAssemblerTransformError,
    transform_jena_assembler_to_queryables,
)

router = APIRouter(tags=["Management"])
config_router = APIRouter(tags=["Configuration"])

log = logging.getLogger(__name__)


@router.get("/", summary="Home page", tags=["Prez"])
async def index(request: Request, system_repo: Repo = Depends(get_system_repo)):
    """Returns the following information about the API"""
    pmts = NegotiatedPMTs(
        headers=request.headers,
        params=request.query_params,
        classes=[PREZ.Object],
        system_repo=system_repo,
    )
    await pmts.setup()
    g = Graph()
    g.bind("prez", "https://prez.dev/")
    g.bind("ont", "https://prez.dev/ont/")
    g.add((URIRef(settings.system_uri), PREZ.version, Literal(settings.prez_version)))
    g.add(
        (
            URIRef(settings.system_uri),
            PREZ.sparqlEndpointEnabled,
            Literal(
                settings.enable_sparql_endpoint,
                datatype=URIRef("http://www.w3.org/2001/XMLSchema#boolean"),
            ),
        )
    )
    g += endpoints_graph_cache
    g += await return_annotation_predicates()
    return await return_from_graph(
        graph=g,
        mediatype=pmts.selected["mediatype"],
        profile=pmts.selected["profile"],
        profile_headers=pmts.generate_response_headers(),
        selected_class=pmts.selected["class"],
        repo=system_repo,
        system_repo=system_repo,
    )


@router.get("/purge-tbox-cache", summary="Reset Tbox Cache")
async def purge_tbox_cache():
    """Purges the tbox cache, then re-adds annotations from common ontologies Prez has a copy of
    (reference_data/annotations)."""
    cache = caches.get("default")
    cache_size = len(cache._cache)
    result = await cache.clear()
    if result and cache_size > 0:
        return PlainTextResponse(f"{cache_size} terms removed from tbox cache.")
    elif result and cache_size == 0:
        return PlainTextResponse("Tbox cache already empty.")
    elif not result:
        raise Exception("Internal Error: Tbox cache not purged.")


@router.get("/tbox-cache", summary="Show the Tbox Cache")
async def return_tbox_cache(request: Request):
    """gets the mediatype from the request and returns the tbox cache in this mediatype"""
    mediatype = request.headers.get("Accept").split(",")[0]
    if not mediatype or mediatype not in RDF_MEDIATYPES:
        mediatype = "text/turtle"
    cache = caches.get("default")
    cache_g = Graph()
    cache_dict = cache._cache
    for subject, pred_obj_bytes in cache_dict.items():
        # use pickle to deserialize the pred_obj_bytes
        pred_obj = pickle.loads(pred_obj_bytes)
        for pred, obj in pred_obj:
            if (
                pred_obj
            ):  # cache entry for a URI can be empty - i.e. no annotations found for URI
                # Add the expanded triple (subject, predicate, object) to 'annotations_g'
                cache_g.add((subject, pred, obj))
    return await return_rdf(cache_g, mediatype, profile_headers={})


@router.get("/health")
async def health_check():
    return {"status": "ok"}


async def get_turtle_request_body(
    request: Request,
    content_type: Annotated[Optional[str], Header()] = None,
) -> str:
    if content_type is None or "text/turtle" not in content_type:
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be text/turtle.",
        )
    return (await request.body()).decode("utf-8")


@router.post(
    "/jena-assembler-to-queryables",
    summary="Debug: transform Jena assembler Turtle into queryables Turtle",
    description=(
        "Pure transform endpoint for inspection/debugging. "
        "Does not load queryables into the running instance. "
        "Use jena_assembler_path for normal startup loading."
    ),
)
async def jena_assembler_to_queryables(
    assembler_turtle: Annotated[str, Depends(get_turtle_request_body)],
    runtime_settings: Annotated[Settings, Depends(get_runtime_settings)],
):
    if not runtime_settings.jena_fuseki_dataset_name:
        raise HTTPException(
            status_code=400,
            detail="jena_fuseki_dataset_name must be set to use this transform endpoint.",
        )

    assembler_graph = Graph()
    try:
        assembler_graph.parse(data=assembler_turtle, format="turtle")
        queryables_graph = transform_jena_assembler_to_queryables(
            assembler_graph,
            runtime_settings.jena_fuseki_dataset_name,
        )
    except JenaAssemblerTransformError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Turtle body: {exc}")

    return Response(
        content=queryables_graph.serialize(format="turtle"),
        media_type="text/turtle",
    )


async def return_annotation_predicates():
    """
    Returns an RDF linked list of the annotation predicates used for labels, descriptions and provenance.
    """
    g = Graph()
    g.bind("prez", "https://prez.dev/")
    label_list_bn, description_list_bn, provenance_list_bn, other_list_bn = (
        BNode(),
        BNode(),
        BNode(),
        BNode(),
    )
    g.add((PREZ.AnnotationPropertyList, PREZ.labelList, label_list_bn))
    g.add((PREZ.AnnotationPropertyList, PREZ.descriptionList, description_list_bn))
    g.add((PREZ.AnnotationPropertyList, PREZ.provenanceList, provenance_list_bn))
    g.add((PREZ.AnnotationPropertyList, PREZ.otherList, other_list_bn))
    Collection(g, label_list_bn, settings.label_predicates)
    Collection(g, description_list_bn, settings.description_predicates)
    Collection(g, provenance_list_bn, settings.provenance_predicates)
    Collection(g, other_list_bn, settings.other_predicates)
    return g


@router.get("/prefixes", summary="Show prefixes known to prez")
async def show_prefixes(
    mediatype: Optional[NonAnnotatedRDFMediaType | JSONMediaType] = Query(
        default=NonAnnotatedRDFMediaType.TURTLE, alias="_mediatype"
    )
):
    """Returns the prefixes known to prez"""
    mediatype_str = str(mediatype.value)
    ns_map = {pfx: ns for pfx, ns in prefix_graph.namespaces()}
    if mediatype_str == "application/json":
        content = io.BytesIO(json.dumps(ns_map).encode("utf-8"))
    else:
        g = Graph()
        for prefix, namespace in ns_map.items():
            bn = BNode()
            g.add((bn, VANN.preferredNamespacePrefix, Literal(prefix)))
            g.add((bn, VANN.preferredNamespaceUri, Literal(namespace)))
        content = io.BytesIO(g.serialize(format=mediatype_str, encoding="utf-8"))
    return StreamingResponse(content=content, media_type=mediatype_str)


@config_router.post("/configure-endpoints", summary="Configuration")
async def submit_config(
    config: RootModel = Body(..., examples=[configure_endpoings_example])
):
    try:
        create_endpoint_rdf(config.model_dump())
        return {
            "message": f"Configuration received successfully. {len(config.routes)} routes processed."
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@config_router.get("/configure-endpoints")
async def open_config_page():
    """Redirects to the endpoint configuration page"""
    return Response(
        status_code=302, headers={"Location": "/static/endpoint_config.html"}
    )
