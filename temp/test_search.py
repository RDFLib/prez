from rdflib import RDFS

from prez.sparql.search_query import SearchQuery

# from temp.grammar import SearchQuery

test = SearchQuery(
    search_term="test",
    pred_vals=[RDFS.label],
    limit=10,
    offset=0,
).render()
print("")
