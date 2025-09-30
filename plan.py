"""plan.py

pseudocode implementation of pivot functionality

issues:
---

PrezQueryConstructor takes the where clause triples and duplicates them in the
construct clause. But the pivot functionality requires that the construct clause
triples are different to the where clause triples.

i.e.

construct {
  ?s ?node1 ?node2
}
where {
  ?s <pred1> ?node1 .
  ?s <pred2> ?node2 .
}

changes required in:
---
* shacl.py:NodeShape()
* shacl.py:PropertyShape()
* umbrella.py:PrezQueryConstructor()


notes:
---

[ NOTE: actually it looks like tss_list is only used for the construct clause ]
might need to split tss_list into where_clause_tss_list and construct_clause_tss_list
  ( on both NodeShape and PropertyShape objects )

  impacts:

  'anot+' mediatypes inject extra triples into the profile_nodeshape.tss_list before handing to
  object_function or listing_function.
  if tss_list is split then we would need to account for this.

"""

SHEXT = ...
SH = ...


# shacl.py
# ----------------------------------------------------------------------------------------------------
class Path: ...


class NodeShape:
    def from_graph(self):
        self.property_shape_uris = [...]
        self.property_shapes = [PropertyShape(uri) for uri in self.property_shape_uris]
        ...


class PropertyShape:
    def from_graph(self):
        ...
        pivot_node_uri = self.graph.objects(self.uri, SHEXT.pivotNode)
        if pivot_node_uri:
            pivot_node_path = self.graph.objects(pivot_node_uri, SH.path)
            pivot_key_path = self.graph.objects(self.uri, SHEXT.pivotKey)
            pivot_value_path = self.graph.objects(self.uri, SHEXT.pivotValue)
            pivot_paths = (pivot_node_path, pivot_key_path, pivot_value_path)
            if not all(pivot_paths):
                raise "you need to specify a sh:path shext:pivotKey path and a shext:pivotValue path"
                # TODO:
                # 1. inject pivot_node_path to key/value paths
                # 2. call _add_path_to_shape for node/key/value paths
                ...

    def _generate_sparql_from_paths(self):
        for property_path in self.property_paths:
            ...
            if next(self.graph.objects((self.uri, SHEXT.pivotNode)), None):
                # then we are in a pivot profile
                pivot_profile = True
                ...
            if isinstance(property_path, Path):
                # TODO:
                # 1. determine if path is shext:pivotKey path or shext:pivotValue path
                # 2. store sparql_grammar variable for the shext:pivotKey path and shext:pivotValue path
                # 3. add triple to tss_list like:
                #
                #     (self.focus_node, keypath_var, valuepath_var)
                if pivot_profile:
                    ...
                ...
        ...


# ----------------------------------------------------------------------------------------------------
# umbrella.py
# ...
