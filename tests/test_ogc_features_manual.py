from rdflib import Graph
from rdflib.namespace import RDF, GEO


def test_ogc_features_root(client):
    r = client.get(f"/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features")
    assert r.status_code == 200


#
# def test_bbox_query(client):
#     r = client.get(f"/catalogs/ex:DemoCatalog/collections/ex:GeoDataset/features/collections/ex:FeatureCollection/items?bbox=4.0,4.0,6.0,6.0")
#     assert r.status_code == 200
#     g = Graph().parse(data=r.text, format="turtle")
#     # this should filter one feature but not the other
#     assert len(list(g.triples((None, RDF.type, GEO.Feature)))) == 1
