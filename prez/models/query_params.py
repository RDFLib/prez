import json
from typing import Optional, List

from fastapi import HTTPException, Query, Depends

# TODO auto generate allowed mediatypes based on mediatypes referenced in profiles
ALLOWED_MEDIA_TYPES = {
    "application/sparql-query",
    "application/ld+json",
    "application/anot+ld+json",
    "application/rdf+xml",
    "text/turtle",
    "text/anot+turtle",
    "application/n-triples",
    "application/anot+n-triples",
}

ALLOWED_OGC_FEATURES_COLLECTIONS_MEDIA_TYPES = {
    "application/json",
    "text/turtle",
    "application/sparql-query"
}

ALLOWED_OGC_FEATURES_INSTANCE_MEDIA_TYPES = {
    "application/geo+json",
    "text/turtle",
    "application/sparql-query"
}


def reformat_bbox(
        bbox: List[str] = Query(
            default=[],
            description="Bounding box coordinates",
            alias="bbox",
            openapi_extra={
                "name": "bbox",
                "in": "query",
                "required": False,
                "schema": {
                    "type": "array",
                    "oneOf": [
                        {"minItems": 4, "maxItems": 4},
                        {"minItems": 6, "maxItems": 6}
                    ],
                    "items": {
                        "type": "number"
                    }
                },
                "style": "form",
                "explode": False
            }
        )) -> List[float]:
    if bbox:
        return [float(x) for x in bbox[0].split(',')]
    return None


class QueryParams:
    """
    Not using Pydantic as cannot pass descriptions through to OpenAPI docs when using Pydantic.
    See: https://stackoverflow.com/a/64366434/15371702
    """

    def __init__(
            self,
            mediatype: Optional[str] = Query(
                "text/anot+turtle", alias="_mediatype", description="Requested mediatype"
            ),
            profile: Optional[str] = Query(
                None, alias="_profile", description="Requested profile"
            ),
            page: Optional[int] = Query(
                1, ge=1, description="Page number, must be greater than 0"
            ),
            per_page: Optional[int] = Query(
                20,
                ge=1,
                le=100,
                description="Number of items per page, must be greater than 0",
            ),
            bbox: List[float] = Depends(reformat_bbox),
            q: Optional[str] = Query(
                None, description="Search query", example="building"
            ),
            filter: Optional[str] = Query(
                None,
                description="CQL JSON expression.",
            ),
            order_by: Optional[str] = Query(
                None, description="Optional: Field to order by"
            ),
            order_by_direction: Optional[str] = Query(
                None,
                regex="^(ASC|DESC)$",
                description="Optional: Order direction, must be 'ASC' or 'DESC'",
            ),
    ):
        self.q = q
        self.page = page
        self.per_page = per_page
        self.bbox = bbox
        self.order_by = order_by
        self.order_by_direction = order_by_direction
        self.filter = filter
        self.mediatype = mediatype
        self.profile = profile
        self.validate_mediatype()
        self.validate_filter()

    def validate_mediatype(self):
        if self.mediatype and self.mediatype not in ALLOWED_MEDIA_TYPES:
            raise HTTPException(
                status_code=400, detail=f"Invalid media type: {self.mediatype}"
            )

    def validate_filter(self):
        if self.filter:
            try:
                json.loads(self.filter)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Filter criteria must be valid JSON."
                )


class OGCFeaturesQueryParams:
    """
    Not using Pydantic as cannot pass descriptions through to OpenAPI docs when using Pydantic.
    See: https://stackoverflow.com/a/64366434/15371702

    For bbox, require workaround as Pydantic does not support lists of query parameters in the form ?bbox=1,2,3,4
    https://github.com/fastapi/fastapi/issues/2500
    """
    def __init__(
            self,
            mediatype: Optional[str] = Query(
                "application/geo+json", alias="_mediatype", description="Requested mediatype"
            ),
            page: Optional[int] = Query(
                1, ge=1, description="Page number, must be greater than 0"
            ),
            per_page: Optional[int] = Query(
                10,
                ge=1,
                le=10000,
                description="Number of items per page, must be 1<=limit<=10000",
                alias="limit",
            ),
            bbox: List[float] = Depends(reformat_bbox),
            filter: Optional[str] = Query(
                None,
                description="CQL JSON expression.",
            ),
            order_by: Optional[str] = Query(
                None, description="Optional: Field to order by"
            ),
            order_by_direction: Optional[str] = Query(
                None,
                regex="^(ASC|DESC)$",
                description="Optional: Order direction, must be 'ASC' or 'DESC'",
            ),
    ):
        self.page = page
        self.per_page = per_page
        self.bbox = bbox
        self.order_by = order_by
        self.order_by_direction = order_by_direction
        self.filter = filter
        self.mediatype = mediatype
        self.validate_filter()

    def validate_filter(self):
        if self.filter:
            try:
                json.loads(self.filter)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Filter criteria must be valid JSON."
                )

    def validate_bbox(self):
        if self.bbox:
            if len(self.bbox) not in (4, 6):
                raise HTTPException(
                    status_code=400, detail="bbox must have either 4 or 6 coordinates"
                )
            return self.bbox
        return None
