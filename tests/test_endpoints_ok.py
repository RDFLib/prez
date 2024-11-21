import logging
import time
from typing import Optional, Set

from rdflib import Graph

from prez.reference_data.prez_ns import PREZ

log = logging.getLogger(__name__)


def wait_for_app_to_be_ready(client, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = client.get("/health")
            if response.status_code == 200:
                return
        except Exception as e:
            print(e)
        time.sleep(0.5)
    raise RuntimeError("App did not start within the specified timeout")


def ogcprez_links(
    client, visited: Optional[Set] = None, link="/catalogs", total_links_visited=0
):
    if not visited:
        visited = set()
    response = client.get(link)
    g = Graph().parse(data=response.text, format="turtle")
    links = list(g.objects(None, PREZ.link))
    member_bnode_list = list(g.objects(None, PREZ.members))
    if member_bnode_list:
        member_bnode = member_bnode_list[0]
        member_links = list(g.objects(member_bnode, PREZ.link))
        links.extend(member_links)
    assert response.status_code == 200
    for next_link in links:
        print(next_link)
        if next_link not in visited:
            visited.add(next_link)
            # Make the recursive call and update the total_links_visited
            # and visited set with the returned values
            visited, total_links_visited = ogcprez_links(
                client, visited, str(next_link), total_links_visited + 1
            )
    # Return the updated count and visited set
    return visited, total_links_visited


def test_visit_all_links(client):
    visited_links, total_count = ogcprez_links(client)
    print(f"Total links visited: {total_count}")
