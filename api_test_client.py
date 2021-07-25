"""A small utility for testing NvsVocPrez instances

Run from the command line like this:

~$ python api_test_client.py http://localhost:5000

You will need packages listed in requirements.api_test_client.txt installed.

Adjust the script directly to test the various endpoint collections - commented out tests
"""

from typing import Tuple, List, Optional
import httpx
from httpx import ConnectError
from prettytable import PrettyTable
import sys
from rdflib import Graph
import datetime


def get_endpoint(name: str, uri: str) -> Tuple[str, str, int, str, float]:
    try:
        r = httpx.get(uri, timeout=60)
    except ConnectError as e:
        return name, uri, 0, "Connection Error", 0

    if 200 <= r.status_code < 300:
        msg = ""
    elif r.status_code == 500:
        msg = "Internal Server Error"
    else:
        msg = r.text
    return name, str(r.url), r.status_code, msg, r.elapsed.total_seconds()


def check_rdf_from_endpoint(name: str, uri: str) -> Tuple[str, str, int, str, float]:
    try:
        s = datetime.datetime.now()
        g = Graph().parse(uri)
        e = datetime.datetime.now()
        td = e - s
        return name, uri, 200, f"{len(g)} triples", td.total_seconds()
    except ConnectError as e:
        return name, uri, 0, "Connection Error", 0


def run_endpoint_tests(endpoints: List[Tuple[str, str, Optional[str]]]):
    x = PrettyTable()
    x.field_names = ["Name", "Endpoint", "Status", "Response", "Time (s)"]

    for endpoint in endpoints:
        r0 = get_endpoint(endpoint[0], endpoint[1])
        x.add_row([r0[0], r0[1], r0[2], r0[3], r0[4]])

    x.align = "l"
    print(x)


def run_one_endpoint_test(endpoint):
    print(f"testing {endpoint[0]}...")
    x = PrettyTable()
    x.field_names = ["Name", "Endpoint", "Status", "Response", "Time (s)"]

    r0 = get_endpoint(endpoint[0], endpoint[1])

    x.add_row([r0[0], r0[1], r0[2], r0[3], r0[4]])
    x.align = "l"
    print(x)


def make_endpoints(system_uri: str):
    system_uri = system_uri.rstrip("/")
    fast_endpoints = [
        ("System home page", f"{system_uri}", None),
        ("SPARQL Page", f"{system_uri}/sparql", None),
        ("About Page", f"{system_uri}/about", None),
        # ("Contact Page", f"{system_uri}/contact", None),
        ("Vocabularies", f"{system_uri}/collection/", None),
        ("Thesauri", f"{system_uri}/scheme/", None),
        ("standard_name", f"{system_uri}/standard_name/", None),
        ("A Vocabulary, R19", f"{system_uri}/collection/R19/current/", None),
        ("A Thesaurus, WCATHES", f"{system_uri}/scheme/WCATHES/current/", None),
        ("A Concept, S0700046", f"{system_uri}/collection/S07/current/S0700046/", None),
        ("A Mapping, 337272", f"{system_uri}/mapping/I/337272/", None),
        ("standard_name Concept, acoustic_...", f"{system_uri}/standard_name/acoustic_signal_roundtrip_travel_time_in_sea_water/", None),
    ]

    extended_endpoints = [
        ("System home page, NVS Turtle", f"{system_uri}?_mediatype=text/turtle"),
        ("Vocabularies, NVS Turtle", f"{system_uri}/collection/?_mediatype=text/turtle"),
        ("Thesauri, NVS Turtle", f"{system_uri}/scheme/?_mediatype=text/turtle"),
        ("A Vocabulary, R19, NVS Turtle", f"{system_uri}/collection/R19/current/?_mediatype=text/turtle"),
        ("A Thesaurus, WCATHES, NVS Turtle", f"{system_uri}/scheme/WCATHES/current/?_mediatype=text/turtle"),
        ("A Concept, S0700046, NVS Turtle", f"{system_uri}/collection/S07/current/S0700046/?_mediatype=text/turtle"),
        ("A Mapping, 337272, NVS Turtle", f"{system_uri}/mapping/I/337272/?_mediatype=text/turtle"),
        ("standard_name Concept, acoustic_...",
         f"{system_uri}/standard_name/acoustic_signal_roundtrip_travel_time_in_sea_water/?_mediatype=text/turtle"),
        ("A PUV Concept, S0700046, NVS HTML", f"{system_uri}/collection/S07/current/S0700004/"),
        ("A PUV Concept, S0700046, PUV HTML", f"{system_uri}/collection/S07/current/S0700004/?_profile=puv&_mediatype=text/html"),
        ("A PUV Concept, S0700046, PUV Turtle",
         f"{system_uri}/collection/S07/current/S0700004/?_profile=puv&_mediatype=text/turtle"),
    ]

    slow_endpoints = [
        ("EMODNET_PEST HTML", f"{system_uri}/scheme/EMODNET_PEST/current/"),
        ("P01 HTML", f"{system_uri}/collection/P01/current/"),
        ("standard_name HTML", f"{system_uri}/standard_name/"),
    ]

    return fast_endpoints, extended_endpoints, slow_endpoints


def make_rdf_endpoints(system_uri: str):
    return [
        ("System Home", f"{system_uri}", None),
        ("Collections", f"{system_uri}/collection/", None),
        ("Collection R19", f"{system_uri}/collection/R19/current/", None),
        ("Schemes", f"{system_uri}/scheme/", None),
        ("Scheme EMODNET_PEST", f"{system_uri}/scheme/EMODNET_PEST/current/", None),
        ("Mapping 340398", f"{system_uri}/mapping/I/340398/", None),
    ]


def run_rdf_endpoint_tests(endpoints: List[Tuple[str, str, Optional[str]]]):
    x = PrettyTable()
    x.field_names = ["Name", "Endpoint", "Status", "Response", "Time (s)"]

    for endpoint in endpoints:
        print(f"test {endpoint[0]}")
        r0 = check_rdf_from_endpoint(endpoint[0], endpoint[1])
        x.add_row([r0[0], r0[1], r0[2], r0[3], r0[4]])

    x.align = "l"
    print(x)


if __name__ == "__main__":
    sys_uri = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    fast, extended, slow = make_endpoints(sys_uri)
    print(fast)

    # print("Testing fast endpoints...")
    # run_endpoint_tests(fast)

    # print("Testing extended endpoints...")
    # run_endpoint_tests(extended)

    # print("Testing slow endpoints...")
    # run_one_endpoint_test(slow[0])  # EMODNET_PEST
    # run_one_endpoint_test(slow[1])  # P01
    # run_one_endpoint_test(slow[2])  # standard_name

    # run_endpoint_tests(slow)
    # e = make_rdf_endpoints(sys_uri)
    # run_rdf_endpoint_tests(e)
