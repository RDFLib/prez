from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import AnyUrl, BaseModel, Field

from prez.config import settings

########################################################################################################################
# Landing Page


class Link(BaseModel):
    href: str
    rel: str
    type: str
    title: Optional[str] = None


class Links(BaseModel):
    links: List[Link]


class OGCFeaturesLandingPage(BaseModel):
    title: str
    description: str
    links: List[Link]


def generate_landing_page_links(url):
    url_path = url.path
    link_dicts = [
        {
            "href": f"{settings.system_uri}{url_path}",
            "rel": "self",
            "type": "application/json",
            "title": "this document",
        },
        {
            "href": f"{settings.system_uri}{url_path}openapi.json",
            "rel": "service-desc",
            "type": "application/vnd.oai.openapi+json;version=3.1",
            "title": "the API definition",
        },
        {
            "href": f"{settings.system_uri}{url_path}docs",
            "rel": "service-doc",
            "type": "text/html",
            "title": "the API definition",
        },
        {
            "href": f"{settings.system_uri}{url_path}conformance",
            "rel": "conformance",
            "type": "application/json",
            "title": "OGC API conformance classes implemented by this server",
        },
        {
            "href": f"{settings.system_uri}{url_path}collections",
            "rel": "data",
            "type": "application/json",
            "title": "Information about the feature collections",
        },
        {
            "href": f"{settings.system_uri}{url_path}queryables",
            "rel": "http://www.opengis.net/def/rel/ogc/1.0/queryables",
            "type": "application/schema+json",
            "title": "Global Queryables",
        },
    ]
    return [Link(**link) for link in link_dicts]


########################################################################################################################
# Conformance


class ConformanceDeclaration(BaseModel):
    conformsTo: List[str]


CONFORMANCE_CLASSES = [
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
]


########################################################################################################################
# Collection and Collections


class Extent(BaseModel):
    pass


class Collection(BaseModel):
    id: str = Field(
        ..., description="identifier of the collection used, for example, in URIs"
    )
    title: Optional[str] = Field(
        None, description="human readable title of the collection"
    )
    description: Optional[str] = Field(
        None, description="a description of the features in the collection"
    )
    links: List[Link]
    extent: Optional[Extent] = None
    itemType: str = Field(
        default="feature",
        description="indicator about the type of the items in the collection (the default value is 'feature').",
    )
    crs: List[str] = Field(
        default=["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
        description="the list of coordinate reference systems supported by the service",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "address",
                "title": "address",
                "description": "An address.",
                "links": [
                    {"href": "http://data.example.com/buildings", "rel": "item"},
                    {
                        "href": "http://example.com/concepts/buildings.html",
                        "rel": "describedby",
                        "type": "text/html",
                    },
                ],
                "crs": [
                    "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                    "http://www.opengis.net/def/crs/EPSG/0/4326",
                ],
            }
        }


class Collections(BaseModel):
    links: List[Link]
    collections: List[Collection]

    class Config:
        json_schema_extra = {
            "example": {
                "links": [
                    {"href": "http://data.example.com/collections", "rel": "self"},
                    {"href": "http://data.example.com/", "rel": "parent"},
                ],
                "collections": [
                    {
                        "id": "address",
                        "title": "address",
                        "description": "An address.",
                        "links": [
                            {
                                "href": "http://data.example.com/collections/address",
                                "rel": "item",
                            },
                            {
                                "href": "http://example.com/concepts/address.html",
                                "rel": "describedby",
                                "type": "text/html",
                            },
                        ],
                    }
                ],
            }
        }


########################################################################################################################
# Queryables


class GeometryType(str, Enum):
    POINT = "Point"
    LINESTRING = "LineString"
    POLYGON = "Polygon"
    MULTIPOINT = "MultiPoint"
    MULTILINESTRING = "MultiLineString"
    MULTIPOLYGON = "MultiPolygon"
    GEOMETRYCOLLECTION = "GeometryCollection"


class QueryableProperty(BaseModel):
    title: Optional[str] = Field(
        None, description="Human readable title of the queryable"
    )
    description: Optional[str] = Field(None, description="Description of the queryable")
    type: Optional[str] = Field(
        default="string", description="Data type of the queryable"
    )
    minLength: Optional[int] = Field(
        None, description="Minimum length for string properties"
    )
    maxLength: Optional[int] = Field(
        None, description="Maximum length for string properties"
    )
    enum: Optional[List[Union[str, int]]] = Field(None, description="Enumerated values")
    pattern: Optional[str] = Field(
        None, description="Regex pattern for string properties"
    )
    multipleOf: Optional[float] = Field(
        None, description="Multiple of for numeric properties"
    )
    minimum: Optional[float] = Field(
        None, description="Minimum value for numeric properties"
    )
    exclusiveMinimum: Optional[float] = Field(
        None, description="Exclusive minimum for numeric properties"
    )
    maximum: Optional[float] = Field(
        None, description="Maximum value for numeric properties"
    )
    exclusiveMaximum: Optional[float] = Field(
        None, description="Exclusive maximum for numeric properties"
    )
    format: Optional[Literal["date-time", "date", "time", "duration"]] = Field(
        None, description="Format for temporal properties"
    )
    items: Optional[Union[List[str], List[int]]] = Field(
        None, description="Items for array properties"
    )


class SpatialQueryableProperty(QueryableProperty):
    type: Literal["object"] = "object"
    geometryType: GeometryType = Field(..., description="Type of geometry")
    schema: AnyUrl = Field(
        ..., description="URL to the GeoJSON schema for the geometry type"
    )


class Queryables(BaseModel):
    schema: Literal[
        "https://json-schema.org/draft/2019-09/schema",
        "http://json-schema.org/draft-07/schema#",
    ] = Field(default="https://json-schema.org/draft/2019-09/schema", alias="$schema")
    id: str = Field(
        ..., alias="$id", description="URI of the resource without query parameters"
    )
    type: Literal["object"] = "object"
    title: Optional[str] = Field(None, description="Title of the schema")
    description: Optional[str] = Field(None, description="Description of the schema")
    properties: dict[str, Union[QueryableProperty, SpatialQueryableProperty]] = Field(
        ..., description="Queryable properties"
    )


########################################################################################################################
# generate link headers


def generate_link_header(links: List[Link]) -> str:
    header_links = []
    for link in links:
        header_link = f'<{link.href}>; rel="{link.rel}"; type="{link.type}"'
        if link.title is not None:
            header_link += f'; title="{link.title}"'
        header_links.append(header_link)
    return ", ".join(header_links)
