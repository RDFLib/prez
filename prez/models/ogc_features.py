from typing import List, Optional

from pydantic import BaseModel, Field

from prez.config import settings

########################################################################################################################
# Landing Page

class Link(BaseModel):
    href: str
    rel: str
    type: str
    title: Optional[str] = None


class OGCFeaturesLandingPage(BaseModel):
    title: str
    description: str
    links: List[Link]


def generate_landing_page_links(url_path):
    return [
        {
            "href": f"{settings.system_uri}{url_path}",
            "rel": "self",
            "type": "application/json",
            "title": "this document",
        },
        {
            "href": f"{settings.system_uri}{url_path}docs",
            "rel": "service-desc",
            "type": "application/vnd.oai.openapi+json;version=3.1",
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
            "title": "Information about the feature collections"
        }
    ]

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
    id: str = Field(..., description="identifier of the collection used, for example, in URIs")
    title: Optional[str] = Field(None, description="human readable title of the collection")
    description: Optional[str] = Field(None, description="a description of the features in the collection")
    links: List[Link]
    extent: Optional[Extent] = None
    itemType: str = Field(default="feature",
                          description="indicator about the type of the items in the collection (the default value is 'feature').")
    crs: List[str] = Field(
        default=["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
        description="the list of coordinate reference systems supported by the service"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "address",
                "title": "address",
                "description": "An address.",
                "links": [
                    {"href": "http://data.example.com/buildings", "rel": "item"},
                    {"href": "http://example.com/concepts/buildings.html", "rel": "describedby", "type": "text/html"}
                ],
                "crs": [
                    "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                    "http://www.opengis.net/def/crs/EPSG/0/4326"
                ]
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
                    {"href": "http://data.example.com/", "rel": "parent"}
                ],
                "collections": [
                    {
                        "id": "address",
                        "title": "address",
                        "description": "An address.",
                        "links": [
                            {"href": "http://data.example.com/collections/address", "rel": "item"},
                            {"href": "http://example.com/concepts/address.html", "rel": "describedby",
                             "type": "text/html"}
                        ]
                    }
                ]
            }
        }


