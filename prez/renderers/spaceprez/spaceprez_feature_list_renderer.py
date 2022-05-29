from typing import Dict, Optional, Union

from connegp import MEDIATYPE_NAMES
from fastapi.responses import Response, JSONResponse, PlainTextResponse

from models.spaceprez import SpacePrezFeatureList
from renderers import ListRenderer
from utils import templates


class SpacePrezFeatureListRenderer(ListRenderer):
    def __init__(
        self,
        request: object,
        profiles: dict,
        default_profile: str,
        instance_uri: str,
        label: str,
        comment: str,
        feature_list: SpacePrezFeatureList,
        page: int,
        per_page: int,
        member_count: int,
    ) -> None:
        super().__init__(
            request,
            profiles,
            default_profile,
            instance_uri,
            feature_list.members,
            label,
            comment,
            page,
            per_page,
            member_count,
        )
        self.feature_list = feature_list

    def _render_oai_html(self, template_context: Union[Dict, None]):
        """Renders the HTML representation of the OAI profile for a list of features"""
        _template_context = {
            "request": self.request,
            "members": self.members,
            "dataset": self.feature_list.dataset,
            "collection": self.feature_list.collection,
            "uri": self.instance_uri,
            "pages": self.pages,
            "label": self.label,
            "comment": self.comment,
            "profiles": self.profiles,
            "default_profile": self.default_profile_token,
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
        """Renders the JSON representation of the OAI profile for a list of features"""
        content = {
            "links": [
                {
                    "href": str(self.request.url),
                    "rel": "self",
                    "type": self.mediatype,
                    "title": "this document",
                },
                {
                    "href": str(self.request.base_url)[:-1]
                    + str(self.request.url.path),
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
        """Renders the OAI profile for a list of features"""
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
        self, template_context: Optional[Dict] = None
    ) -> Union[
        PlainTextResponse, templates.TemplateResponse, Response, JSONResponse, None
    ]:
        if self.error is not None:
            return PlainTextResponse(self.error, status_code=400)
        elif self.profile == "mem":
            return self._render_mem(template_context)
        elif self.profile == "alt":
            return self._render_alt(template_context)
        elif self.profile == "oai":
            return self._render_oai(template_context)
        elif self.profile == "dd":
            return self._render_dd()
        else:
            return None
