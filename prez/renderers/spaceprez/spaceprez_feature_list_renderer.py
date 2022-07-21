from typing import Dict, Optional, Union

from connegp import MEDIATYPE_NAMES
from fastapi.responses import Response, JSONResponse, PlainTextResponse

from prez.config import *
from prez.models.spaceprez import SpacePrezFeatureList
from prez.renderers import ListRenderer
from prez.utils import templates


class SpacePrezFeatureListRenderer(ListRenderer):
    def __init__(
        self,
        request: object,
        instance_uri: str,
        page: int,
        per_page: int,
        member_count: int,
        feature_list: SpacePrezFeatureList,
    ) -> None:
        super().__init__(
            request,
            instance_uri,
            feature_list.members,
            "Feature list",
            "A list of geo:Features",
            page,
            per_page,
            member_count,
            PREZ.FeatureList,
            PREZ.FeatureList,
        )
        self.feature_list = feature_list

    def _render_oai_html(self, template_context: Union[Dict, None]):
        """Renders the HTML representation of the OGC Features Core profile for a list of features"""
        _template_context = {
            "request": self.request,
            "members": self.members,
            "dataset": self.feature_list.dataset,
            "collection": self.feature_list.collection,
            "uri": self.instance_uri if USE_PID_LINKS else str(self.request.url),
            "pages": self.pages,
            "label": self.label,
            "comment": self.comment,
            "profiles": self.profile_details.available_profiles_dict,
            "default_profile": self.profile_details.default_profile,
            "mediatype_names": dict(
                MEDIATYPE_NAMES, **{"application/geo+json": "GeoJSON"}
            ),
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "spaceprez/spaceprez_features.html",
            context=_template_context,
            headers=self.headers,
        )

    def _render_oai_json(self) -> JSONResponse:
        """Renders the JSON representation of the OGC Features Core profile for a list of features"""
        content = {
            "links": [
                {
                    "href": str(self.request.url),
                    "rel": "self",
                    "type": self.mediatype,
                    "title": "this document",
                },
                {
                    "href": str(self.request.url)[:-1] + str(self.request.url.path),
                    "rel": "alternate",
                    "type": "text/html",
                    "title": "this document as HTML",
                },
            ]
        }

        return JSONResponse(
            content=content,
            media_type="application/json",
            headers=self.headers,
        )

    def _render_oai(self, template_context: Union[Dict, None]):
        """Renders the OGC Features Core profile for a list of features"""
        if self.mediatype == "text/html":
            return self._render_oai_html(template_context)
        else:  # else return JSON
            return self._render_oai_json()

    def _render_dd_json(self) -> JSONResponse:
        """Renders the json representation of the dd profile for a list of features"""
        return JSONResponse(
            content=self.feature_list.get_feature_flat_list(),
            media_type="application/json",
            headers=self.headers,
        )

    def _render_dd(self):
        """Renders the dd profile for a list of features"""
        return self._render_dd_json()

    def render(
        self,
        template_context: Optional[Dict] = None,
        alt_profiles_graph: Optional[Graph] = None,
    ) -> Union[
        PlainTextResponse, templates.TemplateResponse, Response, JSONResponse, None
    ]:
        if self.error is not None:
            return PlainTextResponse(self.error, status_code=400)
        elif self.profile == "mem":
            return self._render_mem(template_context)
        elif self.profile == "alt":
            return self._render_alt(template_context, alt_profiles_graph)
        elif self.profile == "oai":
            return self._render_oai(template_context)
        elif self.profile == "dd":
            return self._render_dd()
        else:
            return None
