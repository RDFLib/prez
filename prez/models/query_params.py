import json
from datetime import datetime
from enum import Enum
from typing import Optional, List, Tuple, Union

from fastapi import HTTPException, Query, Depends

NON_ANOT_RDF_MEDIA_TYPES = {
    "application/ld+json",
    "application/rdf+xml",
    "text/turtle",
    "application/n-triples",
}
ANOT_RDF_MEDIA_TYPES = {f"{type_}/anot+{subtype}"
                        for type_, subtype in (mt.split("/") for mt in NON_ANOT_RDF_MEDIA_TYPES)}

SPARQL_QUERY_MEDIA_TYPE = {"application/sparql-query"}
JSON_MEDIA_TYPE = {"application/json"}
GEOJSON_MEDIA_TYPE = {"application/geo+json"}

STANDARD_MEDIA_TYPES = (
        SPARQL_QUERY_MEDIA_TYPE
        | NON_ANOT_RDF_MEDIA_TYPES
        | ANOT_RDF_MEDIA_TYPES
)

ALLOWED_OGC_FEATURES_COLLECTIONS_MEDIA_TYPES = (
        JSON_MEDIA_TYPE
        | NON_ANOT_RDF_MEDIA_TYPES
        | SPARQL_QUERY_MEDIA_TYPE
)

ALLOWED_OGC_FEATURES_INSTANCE_MEDIA_TYPES = (
    GEOJSON_MEDIA_TYPE
    | NON_ANOT_RDF_MEDIA_TYPES
    | SPARQL_QUERY_MEDIA_TYPE
)

DateTimeOrUnbounded = Union[datetime, str, None]


class OrderByDirectionEnum(Enum):
    ASC = "ASC"
    DESC = "DESC"


class FilterLangEnum(Enum):
    CQL_JSON = "cql2-json"


def reformat_bbox(
        bbox: List[str] = Query(
            default=[],  # Australia
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
            },
            example=["113.338953078, -43.6345972634, 153.569469029, -10.6681857235"]
        )) -> List[float]:
    if bbox:
        return [float(x) for x in bbox[0].split(',')]
    return None


def parse_datetime(datetime_str: str) -> Tuple[DateTimeOrUnbounded, DateTimeOrUnbounded]:
    def normalize_and_parse(part: str) -> DateTimeOrUnbounded:
        if not part:
            return None
        if part == '..':
            return '..'
        normalized = part.replace('t', 'T').replace('z', 'Z')
        return datetime.fromisoformat(normalized)

    parts = datetime_str.split('/')
    if len(parts) == 1:
        return normalize_and_parse(parts[0]), None
    elif len(parts) == 2:
        start = normalize_and_parse(parts[0])
        end = normalize_and_parse(parts[1])
        if start == ".." and end == "..":
            raise ValueError("Both parts of the interval cannot be open")
        return start, end
    else:
        raise ValueError("Invalid datetime format")


def validate_datetime(
        datetime: Optional[str] = Query(
            None,
            description=""" Either a date-time or an interval. Date and time expressions adhere to RFC 3339.
  Intervals may be bounded or half-bounded (double-dots at start or end).
  
  Temporal geometries are either a date-time value or a time interval. The parameter value SHALL conform to the following syntax (using ABNF):

    interval-bounded            = date-time "/" date-time
    interval-half-bounded-start = [".."] "/" date-time
    interval-half-bounded-end   = date-time "/" [".."]
    interval                    = interval-closed / interval-half-bounded-start / interval-half-bounded-end
    datetime                    = date-time / interval

  Examples:
  * A date-time: "2018-02-12T23:20:50Z"
  * A bounded interval: "2018-02-12T00:00:00Z/2018-03-18T12:31:12Z"
  * Half-bounded intervals: "2018-02-12T00:00:00Z/.." or "../2018-03-18T12:31:12Z"

  Only features that have a temporal property that intersects the value of
  `datetime` are selected.

  If a feature has multiple temporal properties, it is the decision of the
  server whether only a single temporal property is used to determine
  the extent or all relevant temporal properties.""",
            alias="datetime",
            openapi_extra={
                "name": "datetime",
                "in": "query",
                "required": False,
                "schema": {
                    "type": "string",
                    "examples": [
                        "2018-02-12T23:20:50Z",
                        "2018-02-12T00:00:00Z/2018-03-18T12:31:12Z",
                        "2018-02-12T00:00:00Z/..",
                        "../2018-03-18T12:31:12Z"
                    ]
                },
                "style": "form",
                "explode": False
            }
        )
) -> Optional[tuple]:
    if datetime:
        try:
            return parse_datetime(datetime)
        except ValueError as e:
            raise ValueError(f"Invalid datetime format: {str(e)}")
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
            datetime: Optional[tuple] = Depends(validate_datetime),
            bbox: List[float] = Depends(reformat_bbox),
            filter_lang: Optional[FilterLangEnum] = Query(
                'cql2-json',
                description="Language of the filter expression",
                alias="filter-lang",
            ),
            filter_crs: Optional[str] = Query(
                "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                description="CRS used for the filter expression"
            ),
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
            order_by_direction: Optional[OrderByDirectionEnum] = Query(
                None,
                description="Optional: Order direction, must be 'ASC' or 'DESC'",
            ),
    ):
        self.q = q
        self.page = page
        self.per_page = per_page
        self.datetime = datetime
        self.bbox = bbox
        self.filter_lang = filter_lang
        self.filter_crs = filter_crs
        self.order_by = order_by
        self.order_by_direction = order_by_direction
        self.filter = filter
        self.mediatype = mediatype
        self.profile = profile
        self.validate_mediatype()
        self.validate_filter()

    def validate_mediatype(self):
        if self.mediatype and self.mediatype not in STANDARD_MEDIA_TYPES:
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
            datetime: Optional[tuple] = Depends(validate_datetime),
            bbox: List[float] = Depends(reformat_bbox),
            filter_lang: Optional[FilterLangEnum] = Query(
                'cql2-json',
                description="Language of the filter expression",
                alias="filter-lang",
            ),
            filter_crs: Optional[str] = Query(
                "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                description="CRS used for the filter expression"
            ),
            filter: Optional[str] = Query(
                None,
                description="CQL JSON expression.",
            ),
            order_by: Optional[str] = Query(
                None, description="Optional: Field to order by"
            ),
            order_by_direction: Optional[OrderByDirectionEnum] = Query(
                None,
                description="Optional: Order direction, must be 'ASC' or 'DESC'",
            ),
    ):
        self.page = page
        self.per_page = per_page
        self.bbox = bbox
        self.filter_lang = filter_lang
        self.filter_crs = filter_crs
        self.datetime = datetime
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
