from typing import List, Union, Dict
import re

from connegp.exceptions import *
from connegp.consts import *
from connegp.profile import Profile


class Connegp(object):
    def __init__(
        self, request: object, profiles: Dict[str, Profile], default_profile_token: str
    ) -> None:
        self._request = request
        self._profiles = profiles
        self._default_profile_token = default_profile_token

        self.profile = self._get_profile()
        self.mediatype = self._get_mediatype()

    def _parse_profiles_from_accept_profile_header(self) -> Union[List[Dict], None]:
        """
        Reads an Accept-Profile HTTP header and returns a list of Profile tokens in descending weighted order
        Ref: https://www.w3.org/TR/dx-prof-conneg/#http-getresourcebyprofile
        :return: List of URIs of accept profiles in descending request order
        :rtype: list
        """
        # profile_header = self._request.get("headers").get("Accept-Profile") # Dict
        profile_header = self._request.headers.get("Accept-Profile")  # FastAPI & Flask
        if profile_header is not None:
            try:
                profiles_temp = []
                for val in re.split(", *<", profile_header):
                    try:
                        uri, q = val.split(";", 1)
                    except ValueError:
                        uri, q = val, "q=1"

                    link = {"profile": uri.strip('<> "'), "q": float(q.split("=")[1])}

                    profiles_temp.append(link)
                profiles_temp = sorted(
                    profiles_temp, key=lambda k: k["q"], reverse=True
                )
                profiles = []
                for p in profiles_temp:
                    # convert this valid URI/URN to a token
                    for token, profile in self._profiles.items():
                        if profile.uri == p["profile"]:
                            profiles.append(token)
                if len(profiles) == 0:
                    return None
                else:
                    return profiles
            except Exception:
                msg = "You have requested a profile using an Accept-Profile header that is incorrectly formatted."
                raise ProfilesMediatypesException(msg)
        else:
            return None

    def _parse_profiles_from_qsa(self) -> Union[List[Dict], None]:
        """
        Reads either _profile or _view Query String Argument and returns a list of Profile tokens
        in ascending preference order
        Ref: https://www.w3.org/TR/dx-prof-conneg/#qsa-getresourcebyprofile
        :return: List of URIs of accept profiles in descending request order
        :rtype: list
        """
        # try QSAa and, if we have any, return them only
        # profiles_string = self._request.get("query_params").get("_profile") # Dict
        profiles_string = ""
        # check which framework is being used
        if hasattr(self._request, "query_params"):
            # FastAPI
            profiles_string = self._request.query_params.get("_profile")
        elif hasattr(self._request, "args"):
            # Flask
            profiles_string = self._request.args.get("_profile")
        else:
            raise AttributeError(
                "Python framework not supported. Supported frameworks are: FastAPI, Flask"
            )
        # profiles_string = None  # TODO: Change request from Flask to FastAPI
        if profiles_string is not None:
            qsa_profiles = []

            valid = True
            within = False
            splits = []
            for i, letter in enumerate(profiles_string):
                if letter == "<":
                    within = True
                elif letter == ">":
                    within = False
                elif letter == "," and within is False:
                    splits.append(i)
                else:
                    pass

            profiles = []
            start = 0
            for i, split in enumerate(splits):
                profiles.append(profiles_string[start:split])
                start = splits[i] + 1

            profiles.append(profiles_string[start:])

            for i, profile in enumerate(profiles):
                # if the profile ID is a URI (HTTP URI or a URN) then it must be enclosed in <>
                if "http:" in profile or "https:" in profile or "urn:" in profile:
                    if not profile.startswith("<") and ">" not in profile:
                        valid = False
                        break
                try:
                    p, q = profile.split(";", 1)
                except ValueError:
                    p, q = profile, "q=1"

                profile = {"profile": p, "q": float(q.split("=")[1])}

                qsa_profiles.append(profile)
            qsa_profiles = sorted(qsa_profiles, key=lambda k: k["q"], reverse=True)

            if valid:
                profiles = []
                for p in qsa_profiles:
                    if p["profile"].startswith("<"):
                        # convert this valid URI/URN to a token
                        for token, profile in self._profiles.items():
                            if profile.uri == p["profile"].strip("<>"):
                                profiles.append(token)
                    else:
                        # it's already a token so just add it
                        profiles.append(profile["profile"])

                if len(profiles) > 0:
                    return profiles

        return None

    def _get_available_profiles(self):
        uris = {}
        for token, profile in self._profiles.items():
            uris[profile.uri] = token

        return uris

    def _get_profile(self) -> str:
        # if we get a profile from QSA, use that
        profiles_requested = self._parse_profiles_from_qsa()

        # if not, try Accept-Profile header
        if profiles_requested is None:
            profiles_requested = self._parse_profiles_from_accept_profile_header()

        # if still no profile, return default profile token
        if profiles_requested is None:
            return self._default_profile_token

        # if we have a result from QSA or accept-profile, got through each in order and see if there's an available
        # profile for that token, return first one
        profiles_available = self._get_available_profiles()
        for profile in profiles_requested:
            for k, v in profiles_available.items():
                if profile == v:
                    return v  # return the profile token

        # if no match found, return default profile token
        return self._default_profile_token

    def _parse_mediatypes_from_accept_header(self):
        # mediatypes_accept = self._request.get("headers").get('Accept') # Dict
        mediatypes_accept = self._request.headers.get("Accept")  # FastAPI & Flask
        if mediatypes_accept is not None:
            try:
                # Chrome breaking Accept header variable by adding v=b3
                # Issue https://github.com/RDFLib/pyLDAPI/issues/21
                mediatypes_string = re.sub("v=(.*);", "", mediatypes_accept)

                # split the header into individual URIs, with weights still attached
                mediatypes = mediatypes_string.split(",")

                # remove \s
                mediatypes = [x.strip() for x in mediatypes]

                # split off any weights and sort by them with default weight = 1
                mediatypes = [
                    (
                        float(x.split(";")[1].replace("q=", "")) if ";q=" in x else 1,
                        x.split(";")[0],
                    )
                    for x in mediatypes
                ]

                # sort profiles by weight, heaviest first
                mediatypes.sort(reverse=True)

                # return only the orderd list of mediatypes, not weights
                return [x[1] for x in mediatypes]
            except Exception:
                raise ProfilesMediatypesException(
                    "You have requested a Media Type using an Accept header that is incorrectly formatted."
                )

        return None

    def _parse_mediatypes_from_qsa(self):
        # qsa_mediatypes = self._request.get("query_params").get('_mediatype') # Dict
        qsa_mediatypes = ""
        # check which framework is being used
        if hasattr(self._request, "query_params"):
            # FastAPI
            qsa_mediatypes = self._request.query_params.get("_mediatype")
        elif hasattr(self._request, "args"):
            # Flask
            qsa_mediatypes = self._request.args.get("_mediatype")
        else:
            raise AttributeError(
                "Python framework not supported. Supported frameworks are: FastAPI, Flask"
            )
        if qsa_mediatypes is not None:
            qsa_mediatypes = str(qsa_mediatypes).replace(" ", "+").split(",")
            return qsa_mediatypes
        else:
            return None

    # def _parse_mediatypes_from_link_header(self):
    #     pass

    def _get_available_mediatypes(self):
        return self._profiles[self.profile].mediatypes

    def _get_mediatype(self) -> str:
        mediatypes_requested = self._parse_mediatypes_from_qsa()

        if mediatypes_requested is None:
            mediatypes_requested = self._parse_mediatypes_from_accept_header()

        # no Media Types requested so return default
        if mediatypes_requested is None:
            return self._profiles[self.profile].default_mediatype

        # iterate through requested Media Types until a valid one is found
        mediatypes_available = self._get_available_mediatypes()
        for mediatype in mediatypes_requested:
            if mediatype in mediatypes_available:
                return mediatype

        # no valid Media Type is found so return default
        return self._profiles[self.profile].default_mediatype
