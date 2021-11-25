from typing import List, Dict, Tuple
from pathlib import Path
import uuid

from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, DCTERMS
from rdflib.compare import isomorphic, to_isomorphic

from config import *
from sparql_utils import *


def get_remote_vocabs() -> List[str]:
    """Gets all vocabs in the triplestore"""
    vocabs = []
    results = sparql_query(
        """
        SELECT DISTINCT ?g
        WHERE {
            GRAPH ?g {
                ?s ?p ?o .
            }
            FILTER (!STRSTARTS(STR(?g), "system") && STR(?g) != "background:")
        }
    """
    )

    for result in results:
        vocabs.append(result["g"]["value"])
    return vocabs


def get_graph_uri_for_vocab(vocab: Path) -> URIRef:
    """We can get the Graph URI for a vocab from the vocab file as we know that all VocPub-conformant vocabs
    have one and only one ConceptScheme per file and that the CGI VocPrez installation uses the ConceptScheme URI
    as the Graph URI"""
    g = Graph().parse(str(vocab), format="ttl")
    for s in g.subjects(predicate=RDF.type, object=SKOS.ConceptScheme):
        return s


def get_local_vocabs() -> Dict:
    """Gets all vocabs in the local `vocabularies/` directory"""
    vocabs = {}
    for f in Path(__file__).parent.parent.glob("vocabularies/**/*.ttl"):
        vocabs[str(get_graph_uri_for_vocab(f))] = f

    return vocabs


def get_diff(
    local_vocabs_list: List[str], remote_vocabs: List[str]
) -> Tuple[List[str]]:
    """Gets the difference between the local vocabs and the triplestore vocabs"""
    to_be_added = list(set(local_vocabs_list) - set(remote_vocabs))
    to_be_deleted = list(set(remote_vocabs) - set(local_vocabs_list))
    return (to_be_added, to_be_deleted)


def add_vocabs(vocabs: List[str], local_vocabs: Dict[str, str]):
    """Adds the vocabs flagged for insertion and re-adds all vocabs
    to the default union graph."""

    # add vocab to triplestore
    for vocab in vocabs:
        add_graph(vocab, local_vocabs[vocab])

    # add all local graphs to default
    for vocab in list(local_vocabs.keys()):
        add_to_default(vocab)


def delete_vocabs(vocabs: List[str]):
    """Drops the default union graph from the triplestore and
    deletes vocabs flagged for deletion."""

    # drop default graph
    sparql_update("DROP DEFAULT")

    # drop vocab
    for vocab in vocabs:
        drop_graph(vocab)


def add_graph(graph_uri: str, graph_file: Path) -> None:
    """Adds a graph to the triplestore"""
    d = Dataset()
    content_graph = d.graph(identifier=graph_uri)
    content_graph.parse(graph_file)

    # check for ID, error if has id but not unique
    r = content_graph.query(
        f"""
        PREFIX dcterms: <{DCTERMS}>
        SELECT ?id
        WHERE {{
            <{graph_uri}> dcterms:identifier ?id .
        }}
    """
    )
    if r.bindings:
        id = str(r.bindings[0]["id"])
        for key, value in id_dict.items():
            if value == id and key != graph_uri:
                raise Exception("Provided ID is not unique")

    # create system graph with inference
    system_graph = create_system_graph(graph_uri, content_graph, d)

    # add seeAlso triple to triplestore
    sparql_update(
        f"""
        PREFIX rdfs: <{RDFS}>
        INSERT DATA {{
            GRAPH <system:> {{
                <{graph_uri}> rdfs:seeAlso <{system_graph.identifier}> .
            }}
        }}
    """
    )

    # add system graph to triplestore
    sparql_insert_graph(
        system_graph.identifier, system_graph.serialize(format="turtle")
    )

    # add graph to triplestore
    with open(graph_file, "rb") as f:
        graph_content = f.read()
    sparql_insert_graph(graph_uri, graph_content)

    # update seeAlso dict
    mapping_dict[graph_uri] = str(system_graph.identifier)


def create_id(content_graph: Graph, system_graph: Graph, uri: str) -> str:
    """Creates an ID if doesn't exist & checks for uniqueness"""
    # either get ID or generate one if none exists
    r = content_graph.query(
        f"""
        PREFIX dcterms: <{DCTERMS}>
        CONSTRUCT {{
            ?c dcterms:identifier ?id .
        }}
        WHERE {{
            BIND (<{uri}> as ?c)
            OPTIONAL {{
                ?c dcterms:identifier ?given_id .
            }}
            BIND (REPLACE(STR(?c), ".*[/|#|:](.*)$", "$1") AS ?uri_id)
            BIND (COALESCE(?given_id, ?uri_id) AS ?id)
        }}
    """
    )

    # get generated id as variable
    r2 = r.graph.query(
        f"""
        PREFIX dcterms: <{DCTERMS}>
        SELECT ?id
        WHERE {{
            ?c dcterms:identifier ?id .
        }}
    """
    )
    id = r2.bindings[0]["id"]

    # check for uniqueness, retry once by adding a "1" to the id
    retries = 0
    while retries < 2:
        # check that ID is unique
        if id not in id_dict.values():
            break

        retries += 1
        if retries == 2:
            raise Exception(f"Unable to generate unique ID for {uri}")
        id += 1

    # add ID to system graph
    system_graph.add((URIRef(uri), DCTERMS.identifier, id))

    # update ID dict
    id_dict[uri] = id

    return id


def create_system_graph(
    graph_uri: str, content_graph: Graph, dataset: Dataset
) -> Graph:
    """Creates a system graph for a content graph and populates it with inferred data"""
    system_graph = dataset.graph(identifier=f"system:{uuid.uuid4()}")

    # generate IDs for vocabs, concepts & collections
    r = content_graph.query(
        f"""
        PREFIX skos: <{SKOS}>
        SELECT ?s
        WHERE {{
            ?s a ?o .
            FILTER (?o IN (skos:ConceptScheme, skos:Concept, skos:Collection)) .
        }}
    """
    )
    for binding in r.bindings:
        s_id = create_id(content_graph, system_graph, binding["s"])

    # broader/narrower & hastopconcept/topconceptof/inscheme
    dataset.update(
        f"""
        PREFIX skos: <{SKOS}>
        INSERT {{
            GRAPH <{system_graph.identifier}> {{
                ?a skos:narrower ?b .
                ?c skos:broader ?d .
                ?e skos:topConceptOf <{graph_uri}> ;
                    skos:inScheme <{graph_uri}> .
                <{graph_uri}> skos:hasTopConcept ?f .
                ?f skos:inScheme <{graph_uri}> .
            }}
        }}
        WHERE {{
            GRAPH <{graph_uri}> {{
                ?b skos:broader ?a .
                ?d skos:narrower ?c .
                <{graph_uri}> skos:hasTopConcept ?e .
                ?f skos:topConceptOf <{graph_uri}> .
            }}
        }}
    """
    )
    return system_graph


def add_to_default(graph_uri: str) -> None:
    """Adds a graph to the triplestore's default union graph"""
    sparql_update(f"ADD <{graph_uri}> TO DEFAULT")
    sparql_update(f"ADD <{mapping_dict[graph_uri]}> TO DEFAULT")


def drop_graph(graph_uri: str) -> None:
    """Drops a graph from the triplestore"""
    # delete seeAlso records
    sparql_update(
        f"""
        WITH <system:>
        DELETE {{
            <{graph_uri}> ?p ?o .
        }}
        WHERE {{
            <{graph_uri}> ?p ?o .
        }}
    """
    )
    sparql_update(f"DROP GRAPH <{mapping_dict[graph_uri]}>")
    sparql_update(f"DROP GRAPH <{graph_uri}>")

    # remove from seeAlso & ID dicts
    mapping_dict.pop(graph_uri)
    id_dict.pop(graph_uri)


def get_modified_vocabs(local_vocabs: Dict[str, str]) -> List[str]:
    """Gets a list of the graphs that have been modified"""
    modified = []
    for uri, filename in local_vocabs.items():
        # compare remote vs local graphs
        r = sparql_construct(
            f"""
            CONSTRUCT {{
                ?s ?p ?o .
            }}
            WHERE {{
                GRAPH <{uri}> {{
                    ?s ?p ?o .
                }}
            }}
        """
        )
        g_remote = Graph().parse(data=r, format="turtle")
        if len(g_remote) == 0:  # remote vocab doesn't exist
            continue

        # accounts for bnodes
        g_remote_str = to_isomorphic(g_remote).serialize(format="turtle")
        # re-parsed as namespace order is not guaranteed
        remote = Graph().parse(data=g_remote_str, format="turtle")

        with open(filename, "rb") as f:
            g_local = Graph().parse(f.read(), format="turtle")
        # accounts for bnodes
        g_local_str = to_isomorphic(g_local).serialize(format="turtle")
        # tags that get omitted in remote version
        g_local_str = g_local_str.replace("@en", "")
        g_local_str = g_local_str.replace("^^xsd:string", "")
        # re-parsed as namespace order is not guaranteed
        local = Graph().parse(data=g_local_str, format="turtle")

        # compare graphs are equal
        if not isomorphic(remote, local):
            modified.append(uri)
    return modified


if __name__ == "__main__":
    if DROP_ON_START:
        sparql_update("DROP ALL")
        sparql_update("CREATE GRAPH <system:>")
        sparql_update("CREATE GRAPH <background:>")

        # add ontology files to <background:> graph
        for ont_file in Path(__file__).parent.parent.glob("ontologies/**/*.ttl"):
            with open(ont_file, "rb") as f:
                sparql_insert_graph("background:", f.read())

    # query DB for content graph to system graph map, store in python dict
    r = sparql_query(
        f"""
        PREFIX rdfs: <{RDFS}>
        SELECT ?content ?system
        WHERE {{
            GRAPH <system:> {{
                ?content rdfs:seeAlso ?system .
            }}
        }}
    """
    )
    mapping_dict = {
        result["content"]["value"]: result["system"]["value"] for result in r
    }

    # query DB for all IDs, store in dict for uniqueness checking
    r = sparql_query(
        f"""
        PREFIX dcterms: <{DCTERMS}>
        SELECT ?content ?id
        WHERE {{
            ?content dcterms:identifier ?id .
        }}
    """
    )
    id_dict = {result["content"]["value"]: result["id"]["value"] for result in r}

    # check if id dict has distinct values
    assert len(set(id_dict.values())) == len(id_dict.values()), "Found duplicate IDs"

    # gets remote & local vocabs
    remote_vocabs = get_remote_vocabs()
    print(f"remote vocabs: {remote_vocabs}")
    local_vocabs = get_local_vocabs()  # {uri: file, ...}
    local_vocabs_list = list(local_vocabs.keys())
    print(f"local vocabs: {local_vocabs_list}")

    modified_vocabs = get_modified_vocabs(local_vocabs)
    print(f"modified vocabs: {modified_vocabs}")
    to_be_added, to_be_deleted = get_diff(local_vocabs_list, remote_vocabs)
    print(f"added vocabs: {to_be_added}")
    print(f"removed vocabs: {to_be_deleted}")

    # make changes
    delete_vocabs(to_be_deleted + modified_vocabs)
    add_vocabs(modified_vocabs + to_be_added, local_vocabs)

    # output the changes
    print("added:")
    [print(f" - {vocab}") for vocab in to_be_added] if to_be_added else print(" None")
    print("deleted:")
    [print(f" - {vocab}") for vocab in to_be_deleted] if to_be_deleted else print(
        " None"
    )
    print("modified:")
    [print(f" - {vocab}") for vocab in modified_vocabs] if modified_vocabs else print(
        " None"
    )
