from rdflib import URIRef

from prez.config import settings


class ClassNotFoundException(Exception):
    """
    Raised when no classes can be found for a given URI.
    If the URI is also not found, a URINotFoundException is raised instead.
    """

    def __init__(self, uri: URIRef):
        self.message = f"No classes found for {uri}. Prez can only display information for instances of classes"
        super().__init__(self.message)


class URINotFoundException(Exception):
    """
    Raised when a URI is not found in the triplestore.
    """

    def __init__(self, uri: URIRef):
        self.message = f"URI {uri} not found at endpoint {settings.sparql_endpoint}."
        super().__init__(self.message)


class NoProfilesException(Exception):
    """
    Raised when no profiles can be found for a resource.
    """

    def __init__(self, classes: list):
        self.message = (
            f"No profiles and/or mediatypes could be found to render the resource. The resource class(es) "
            f"for which a profile was searched was/were: {', '.join(klass for klass in classes)}"
        )
        super().__init__(self.message)
