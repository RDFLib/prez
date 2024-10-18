import logging
import re
from urllib.parse import urlparse

from aiocache import caches
from rdflib import URIRef

from prez.cache import prefix_graph
from prez.config import settings

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
    PN_CHARS_BASE = r"([A-Z]|[a-z]|[\u00C0-\u00D6]|[\u00D8-\u00F6]|[\u00F8-\u02FF]|[\u0370-\u037D]|[\u037F-\u1FFF]|[\u200C-\u200D]|[\u2070-\u218F]|[\u2C00-\u2FEF]|[\u3001-\uD7FF]|[\uF900-\uFDCF]|[\uFDF0-\uFFFD]|[\U00010000-\U000EFFFF])"
    PN_CHARS_U = rf"({PN_CHARS_BASE}|_)"
    PN_CHARS = rf"({PN_CHARS_U}|-|[0-9]|\u00B7|[\u0300-\u036F]|[\u203F-\u2040])"
    PN_PREFIX = rf"({PN_CHARS_BASE}(({PN_CHARS}|.)*{PN_CHARS})?)"
    matches = re.match(PN_PREFIX, prefix)
    if not matches:
        valid = False
    return valid


def generate_new_prefix(uri):
    """
    Generates a new prefix for a uri
    """
    parsed_url = urlparse(uri)
    if bool(parsed_url.fragment):
        ns = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}#"
    else:
        ns = f'{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rsplit("/", 1)[0]}/'

    split_prefix_path = ns[:-1].rsplit("/", 1)
    if len(split_prefix_path) > 1:
        to_generate_prefix_from = split_prefix_path[-1].lower()
        # attempt to just use the last part of the path prior to the fragment or "identifier"
        if len(to_generate_prefix_from) <= 6:
            proposed_prefix = to_generate_prefix_from
            if not prefix_registered(proposed_prefix):
                prefix_graph.bind(proposed_prefix, ns)
                return
        # otherwise, remove vowels to reduce length
        proposed_prefix = "".join(
            [c for c in to_generate_prefix_from if c not in "aeiou!@#$%^&*()_+-=,."]
        )
        if not valid_prefix(proposed_prefix):
            # if we still can't get a nice prefix. use an ugly but valid one using a hash of the IRI
            proposed_prefix = f"ns{hash(to_generate_prefix_from)}"
        if not prefix_registered(proposed_prefix):
            prefix_graph.bind(proposed_prefix, ns)
            return
    else:
        raise ValueError("Couldn't generate a prefix for the URI")


def get_curie_id_for_uri(uri: URIRef) -> str:
    """
    This function gets a curie ID for a given URI.
    The following process is used:
    1. Check Prez's in memory prefix graph for an existing prefix for the URI's namespace.
    2. If not found, attempt to generate a "nice" prefix using prez's "generate_new_prefix" function.
    3. If unable to generate a "nice" prefix, use the "compute_qname" function to generate a prefix in the series ns0,
    ns1 etc.
    """
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
    return f"{qname[0]}{separator}{qname[2]}"


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
            raise
        await curie_cache.set(curie_id, uri)
        return uri
