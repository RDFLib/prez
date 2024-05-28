import json
from typing import Optional

from fastapi import HTTPException, Query

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
        q: Optional[str] = Query(None, description="Optional: Search query"),
        filter: Optional[str] = Query(None, description="CQL JSON expression."),
        order_by: Optional[str] = Query(
            None, description="Optional: Field to order by"
        ),
        order_by_direction: Optional[str] = Query(
            None,
            regex="^(asc|desc)$",
            description="Optional: Order direction, must be 'asc' or 'desc'",
        ),
    ):
        self.q = q
        self.page = page
        self.per_page = per_page
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
