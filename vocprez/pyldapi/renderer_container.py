from .renderer import Renderer
from .profile import Profile
from .data import RDF_MEDIATYPES


class ContainerRenderer(Renderer):
    def __init__(self,
                 request,
                 instance_uri,
                 profiles=None,
                 default_profile_token="mem",
                 **kwargs
                 ):

        contanno = Profile(
            uri="https://w3id.org/profile/contanno",
            id="contanno",
            label="Container Annotations",
            comment="Describes container annotations only, that is a veiw of a container object's properties"
                    " other than its members.",
            mediatypes=["text/html"] + RDF_MEDIATYPES,
            default_mediatype="text/html",
            languages=["en"],
            default_language="en",
        )

        mem = Profile(
            uri="https://w3id.org/profile/mem",  # the ConnegP URI for Alt Rep Data Model
            id="mem",
            label="Members",
            comment="A very basic data model that lists the members of container objects only, i.e. not their other "
                    "properties",
            mediatypes=["text/html", "application/json"] + RDF_MEDIATYPES,
            default_mediatype="text/html",
            languages=["en"],
            default_language="en",
        )

        new_profiles = {
            "contanno": contanno,
            "mem": mem,
        }
        if profiles is not None:
            new_profiles.update(profiles)

        super().__init__(
            request,
            str(request.url).split("?")[0],
            new_profiles,
            default_profile_token,
        )

    def render(self):
        alt = super().render()
        if alt is not None:
            return alt
        elif self.profile == "mem":
            raise NotImplementedError("You must implement handling for the mem profile")
        elif self.profile == "contanno":
            raise NotImplementedError("You must implement handling for the contanno profile")