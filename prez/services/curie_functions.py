import logging
import re
import string
from urllib.parse import urlparse

from aiocache import caches
from rdflib import URIRef

from prez.cache import prefix_graph
from prez.config import settings
from prez.exceptions.model_exceptions import PrefixNotBoundException

log = logging.getLogger(__name__)


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


def valid_prefix(prefix: str):
    """For turtle serialization, as per https://www.w3.org/TR/turtle/#grammar-production-PN_PREFIX"""
    valid = True
    PN_CHARS_BASE = "([A-Z]|[a-z]|[\u00c0-\u00d6]|[\u00d8-\u00f6]|[\u00f8-\u02ff]|[\u0370-\u037d]|[\u037f-\u1fff]|[\u200c-\u200d]|[\u2070-\u218f]|[\u2c00-\u2fef]|[\u3001-\ud7ff]|[\uf900-\ufdcf]|[\ufdf0-\ufffd]|[\U00010000-\U000effff])"
    PN_CHARS_U = f"({PN_CHARS_BASE}|_)"
    PN_CHARS = f"({PN_CHARS_U}|-|[0-9]|\u00b7|[\u0300-\u036f]|[\u203f-\u2040])"
    PN_PREFIX = f"({PN_CHARS_BASE}(({PN_CHARS}|.)*{PN_CHARS})?)"
    matches = re.match(PN_PREFIX, prefix)
    if not matches:
        valid = False
    return valid


def generate_new_prefix(uri):
    """
    Generates a new prefix for a uri
    """
    if uri.startswith("urn:"):
        # Special handling for URNs
        ns = uri.rsplit(":", 1)[0] + ":"
        split_prefix_path = ns[:-1].rsplit(":", 1)
    else:
        parsed_url = urlparse(uri)
        if not parsed_url.scheme:
            raise ValueError(
                "The URI must have a scheme (e.g., http, https, file, urn, etc)"
            )
        if bool(parsed_url.fragment):
            ns = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}#"
        else:
            ns = f'{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rsplit("/", 1)[0]}/'
        split_prefix_path = ns[:-1].rsplit("/", 1)
    if len(split_prefix_path) > 1:
        path_part = split_prefix_path[-1]
        # generate a prefix using the last part of the path prior to the fragment or 'identifier'
        # converts to lowercase and removes punctuation characters
        proposed_prefix = path_part.lower().translate(
            str.maketrans("", "", string.punctuation)
        )
        if not valid_prefix(proposed_prefix):
            # if the generated prefix is not valid use an ugly but valid one by hashing the last part of the uri
            proposed_prefix = f"ns{hash(path_part)}"
        if not prefix_registered(proposed_prefix):
            prefix_graph.bind(proposed_prefix, ns)
            return
    else:
        raise ValueError("Couldn't generate a prefix for the URI")


#: uri -> curie. Link generation asks for a curie for every URI in a response, and
#: for the same URIs on every request, while ``compute_qname`` re-splits the URI and
#: walks the namespace manager each time. Bindings only ever grow (the generator
#: binds a namespace the first time it sees one, and keeps it), so an entry stays
#: valid until prefixes are (re)loaded, which calls :func:`clear_curie_cache`.
_curie_cache: dict[str, str] = {}


def clear_curie_cache() -> None:
    """Forget the memoized curies. Call after binding prefixes into the graph."""
    _curie_cache.clear()


def get_curie_id_for_uri(uri: URIRef) -> str:
    """
    This function gets a curie ID for a given URI.
    The following process is used:
    1. Check Prez's in memory prefix graph for an existing prefix for the URI's namespace.
    2. If not found, attempt to generate a "nice" prefix using prez's "generate_new_prefix" function.
    3. If unable to generate a "nice" prefix, use the "compute_qname" function to generate a prefix in the series ns0,
    ns1 etc.
    """
    cached = _curie_cache.get(uri)
    if cached is not None:
        return cached
    separator = settings.curie_separator
    try:
        qname = prefix_graph.compute_qname(uri, generate=False)
    except Exception:
        try:
            generate_new_prefix(
                uri
            )  # this will mostly succeed in generating new prefixes.
        except ValueError:
            pass  # generation failed; function below will generate namespaces in the series ns0, ns1 etc.
        qname = prefix_graph.compute_qname(uri, generate=True)
    curie = f"{qname[0]}{separator}{qname[2]}"
    _curie_cache[uri] = curie
    return curie


async def get_uri_for_curie_id(curie_id: str):
    """
    Returns a URI for a given CURIE id with the specified separator
    """
    curie_cache = caches.get("curies")
    result = await curie_cache.get(curie_id)
    if result:
        return result
    else:
        separator = settings.curie_separator
        curie = curie_id.replace(separator, ":")
        try:
            uri = prefix_graph.namespace_manager.expand_curie(curie)
        except ValueError:
            raise PrefixNotBoundException(prefix=curie.split(":")[0])
        await curie_cache.set(curie_id, uri)
        return uri
