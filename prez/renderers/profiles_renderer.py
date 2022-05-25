from typing import Dict, Optional, Union, List

from fastapi.responses import Response, JSONResponse, PlainTextResponse
from connegp import MEDIATYPE_NAMES

from config import *
from renderers import Renderer

# from profiles.prez_profiles import profiles
from utils import templates


class ProfilesRenderer(Renderer):
    # profiles = {"profiles": profiles}
    # default_profile_token = "profiles"

    def __init__(
        self, request: object, instance_uri: str, prez: Optional[str] = None
    ) -> None:
        super().__init__(
            request,
            ProfilesRenderer.profiles,
            ProfilesRenderer.default_profile_token,
            instance_uri,
        )
        self.prez = prez

    def set_profiles(self, profile_list: List[Dict]) -> None:
        self.profile_list = profile_list

    def _render_profiles_html(
        self, template_context: Union[Dict, None]
    ) -> templates.TemplateResponse:
        """Renders the HTML representation of the profiles profile"""
        _template_context = {
            "request": self.request,
            "uri": self.instance_uri,
            "profile_list": self.profile_list,
            "profiles": self.profiles,
            "prez": self.prez,
            "default_profile": self.default_profile_token,
            "mediatype_names": MEDIATYPE_NAMES,
        }
        if template_context is not None:
            _template_context.update(template_context)
        return templates.TemplateResponse(
            "profiles.html",
            context=_template_context,
            headers=self.headers,
        )

    def _render_profiles_json(self) -> Response:
        """Renders the JSON representation of the profiles profile"""
        return JSONResponse(content=self.profile_list)

    def _render_profiles(self, template_context: Union[Dict, None]):
        """Renders the profiles profile"""
        if self.mediatype == "text/html":
            return self._render_profiles_html(template_context)
        else:  # only other format is JSON
            return self._render_profiles_json()

    def render(
        self, template_context: Optional[Dict] = None
    ) -> Union[
        PlainTextResponse, templates.TemplateResponse, Response, JSONResponse, None
    ]:
        if self.error is not None:
            return PlainTextResponse(self.error, status_code=400)
        elif self.profile == "alt":
            return self._render_alt(template_context)
        elif self.profile == "profiles":
            return self._render_profiles(template_context)
        else:
            return None
