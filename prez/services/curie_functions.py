from urllib.parse import urlparse

from rdflib import URIRef

from prez.cache import (
    prefix_graph
)
from prez.config import settings


def prefix_registered(prefix):
    """
    Checks if a prefix is available for use
    """
    current_prefixes = [pfx2ns[0] for pfx2ns in prefix_graph.namespaces()]
    if prefix in current_prefixes:
        return True
    return False


def namespace_registered(namespace):
    """
    Checks if a namespace is registered
    """
    try:
        prefix_graph.compute_qname(namespace, generate=False)
        return True
    except KeyError:
        return False

def generate_new_prefix(uri):
    """
    Generates a new prefix for a uri
    """
    parsed_url = urlparse(uri)
    if bool(parsed_url.fragment):
        ns = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}#"
        to_generate_prefix_from = parsed_url.fragment.lower()
    else:
        ns = f'{parsed_url.scheme}://{parsed_url.netloc}{"/".join(parsed_url.path.split("/")[:-1])}/'
        to_generate_prefix_from = parsed_url.path.split("/")[-2].lower()
    # attempt to just use the last part of the path prior to the fragment or "identifier"
    if len(to_generate_prefix_from) <= 6:
        proposed_prefix = to_generate_prefix_from
        if not prefix_registered(proposed_prefix):
            prefix_graph.bind(proposed_prefix, ns)
            return
    # otherwise, remove vowels to reduce length
    proposed_prefix = "".join([c for c in to_generate_prefix_from if c not in "aeiou"])
    if not prefix_registered(proposed_prefix):
        prefix_graph.bind(proposed_prefix, ns)
        return
    else:
        # use RDFLib's default ns0, ns1 etc.
        prefix_graph.compute_qname(uri, generate=True)


def get_curie_id_for_uri(uri: URIRef):
    """
    Returns a CURIE with ":" replaced by a given separator, for a given URI
    """
    separator = settings.curie_separator
    try:
        qname = prefix_graph.compute_qname(uri, generate=False)
    except KeyError:
        generate_new_prefix(uri)
        qname = prefix_graph.compute_qname(uri, generate=False)
    return f"{qname[0]}{separator}{qname[2]}"


def get_uri_for_curie_id(curie_id: str):
    """
    Returns a URI for a given CURIE id with the specified separator
    """
    separator = settings.curie_separator
    curie = curie_id.replace(separator, ":")
    return prefix_graph.namespace_manager.expand_curie(curie)
