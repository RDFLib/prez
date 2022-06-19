# a demo client that works with the store.py rin this folder running
import httpx

q = """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT (COUNT(?cs) AS ?count) 
WHERE { 
  ?cs a skos:ConceptScheme 
}"""

r = httpx.get("http://localhost:3030/vocprez", params={"query": q})

assert (
    r.text
    == '{"results": {"bindings": [{"count": {"type": "literal", "value": "1", "datatype": "http://www.w3.org/2001/XMLSchema#integer"}}]}, "head": {"vars": ["count"]}}'
)
