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

    def __init__(self, uri: URIRef = None, curie: str = None):
        if uri:
            self.message = (
                f'URI "{uri}" not found at endpoint {settings.sparql_endpoint}.'
            )
        if curie:
            self.message = f'URI for curie "{curie}" not found at endpoint {settings.sparql_endpoint}.'
        super().__init__(self.message)


class PrefixNotFoundException(Exception):
    """
    Raised when a requested prefix is not found in the triplestore.
    """

    def __init__(self, prefix: str):
        self.message = (
            f'Prefix "{prefix}" not found at endpoint {settings.sparql_endpoint}.'
        )
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


class InvalidSPARQLQueryException(Exception):
    """
    Raised when a SPARQL query is invalid.
    """

    def __init__(self, error: str):
        self.message = f"Invalid SPARQL query: {error}"
        super().__init__(self.message)


class NoEndpointNodeshapeException(Exception):
    """
    Raised when no endpoint nodeshape can be identified for the given classes/relations.
    """

    def __init__(self, ep_uri: str, hierarchy_level: int):
        self.message = (
            f"No relevant nodeshape found for the given endpoint {ep_uri}, hierarchy level "
            f"{hierarchy_level}, and parent URI"
        )
        super().__init__(self.message)
