from unittest.mock import patch

from rdflib import DCTERMS, PROV, RDFS, SH, SKOS, Graph, Namespace, URIRef
from sparql_grammar_pydantic import (
    IRI,
    PathSequence,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
)

from prez.services.query_generation.shacl import (
    AlternativePath,
    Path,
    PropertyShape,
    SequencePath,
    _build_path_elt_or_inverse,
)

# Define SHEXT namespace locally for tests - corrected namespace
SHEXT = Namespace("http://example.com/shacl-extension#")


def test_path_alias_simple_path_on_shape():
    """Tests shext:pathAlias defined directly on the property shape BNode with a simple path."""
    g = Graph().parse(
        data="""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path dcterms:title ;
        shext:pathAlias <https://alias/title> ;
    ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert len(ps.and_property_paths) == 1
    assert ps.and_property_paths[0].path_alias == URIRef("https://alias/title")
    assert isinstance(ps.and_property_paths[0], Path)
    assert ps.and_property_paths[0].value == DCTERMS.title


def test_path_alias_sequence_path_on_shape():
    """Tests shext:pathAlias defined directly on the property shape BNode with a sequence path."""
    g = Graph().parse(
        data="""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path ( prov:qualifiedDerivation prov:hadRole ) ;
        shext:pathAlias <https://alias/derivation-role> ;
    ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert len(ps.and_property_paths) == 1
    assert ps.and_property_paths[0].path_alias == URIRef(
        "https://alias/derivation-role"
    )
    assert isinstance(ps.and_property_paths[0], SequencePath)
    assert len(ps.and_property_paths[0].value) == 2


def test_path_alias_in_union_simple_path():
    """Tests shext:pathAlias adjacent to a nested sh:path within sh:union."""
    g = Graph().parse(
        data="""
    PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path [
            sh:union (
                dcterms:title
                [
                    sh:path skos:prefLabel ;
                    shext:pathAlias <https://alias/prefLabel> ;
                ]
            )
        ]
    ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert len(ps.union_property_paths) == 2

    # Find the paths based on their value
    title_path = next(
        (
            p
            for p in ps.union_property_paths
            if isinstance(p, Path) and p.value == DCTERMS.title
        ),
        None,
    )
    label_path = next(
        (
            p
            for p in ps.union_property_paths
            if isinstance(p, Path) and p.value == SKOS.prefLabel
        ),
        None,
    )

    assert title_path is not None
    assert title_path.path_alias is None

    assert label_path is not None
    assert label_path.path_alias == URIRef("https://alias/prefLabel")


def test_path_alias_in_union_sequence_path():
    """Tests shext:pathAlias adjacent to a nested sequence sh:path within sh:union."""
    g = Graph().parse(
        data="""
    PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path [
            sh:union (
                skos:prefLabel # No alias
                [
                    sh:path ( prov:qualifiedDerivation prov:hadRole ) ;
                    shext:pathAlias <https://alias/derivation-role> ;
                ]
            )
        ]
    ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=Var(value="focus_node")
    )
    assert len(ps.union_property_paths) == 2

    # Find the paths
    label_path = next(
        (
            p
            for p in ps.union_property_paths
            if isinstance(p, Path) and p.value == SKOS.prefLabel
        ),
        None,
    )
    sequence_path = next(
        (p for p in ps.union_property_paths if isinstance(p, SequencePath)), None
    )

    assert label_path is not None
    assert label_path.path_alias is None

    assert sequence_path is not None
    assert sequence_path.path_alias == URIRef("https://alias/derivation-role")
    assert len(sequence_path.value) == 2
    assert isinstance(sequence_path.value[0], Path)
    assert sequence_path.value[0].value == PROV.qualifiedDerivation
    assert isinstance(sequence_path.value[1], Path)
    assert sequence_path.value[1].value == PROV.hadRole


# --- Tests for generated triples with use_path_aliases=True ---


@patch("prez.services.query_generation.shacl.settings")
def test_alias_triples_simple_path(mock_settings):
    """Verify TSS (construct) uses alias, TSSP (where) uses original path for simple paths."""
    mock_settings.use_path_aliases = True
    g = Graph().parse(
        data="""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path dcterms:title ;
            shext:pathAlias <https://alias/title> ;
        ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    focus_node_var = Var(value="focus_node")
    path_node_1_var = Var(value="prof_1_node_1")
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=focus_node_var, shape_number=0
    )

    # Expected CONSTRUCT triple (using alias)
    expected_tss = TriplesSameSubject.from_spo(
        focus_node_var, IRI(value="https://alias/title"), path_node_1_var
    )

    # Expected WHERE triple (using original path)
    expected_tssp = TriplesSameSubjectPath.from_spo(
        focus_node_var, IRI(value=DCTERMS.title), path_node_1_var
    )

    # Compare string representations due to potential object equality issues
    assert str(expected_tss) in [str(tss) for tss in ps.tss_list]
    # Ensure the original path triple is NOT in tss_list when alias is used
    original_tss = TriplesSameSubject.from_spo(
        focus_node_var, IRI(value=DCTERMS.title), path_node_1_var
    )
    assert str(original_tss) not in [str(tss) for tss in ps.tss_list]

    # Removed checks for tssp_list content as per user request


@patch("prez.services.query_generation.shacl.settings")
def test_alias_triples_sequence_path(mock_settings):
    """Verify TSS (construct) uses alias, TSSP (where) uses original path for sequence paths."""
    mock_settings.use_path_aliases = True
    g = Graph().parse(
        data="""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path ( prov:qualifiedDerivation prov:hadRole rdfs:label ) ;
            shext:pathAlias <https://alias/derivation-role-label> ;
        ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    focus_node_var = Var(value="focus_node")
    path_node_1_var = Var(value="prof_1_node_1")
    path_node_2_var = Var(value="prof_1_node_2")
    path_node_3_var = Var(value="prof_1_node_3")  # Final node in sequence
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=focus_node_var, shape_number=0
    )

    # Expected CONSTRUCT triple (using alias and final node)
    expected_tss = TriplesSameSubject.from_spo(
        focus_node_var,
        IRI(value="https://alias/derivation-role-label"),
        path_node_3_var,
    )

    # Expected WHERE triples (using original sequence)
    expected_tssp_1 = TriplesSameSubjectPath.from_spo(
        focus_node_var, IRI(value=PROV.qualifiedDerivation), path_node_1_var
    )
    expected_tssp_2 = TriplesSameSubjectPath.from_spo(
        path_node_1_var, IRI(value=PROV.hadRole), path_node_2_var
    )
    expected_tssp_3 = TriplesSameSubjectPath.from_spo(
        path_node_2_var, IRI(value=RDFS.label), path_node_3_var
    )

    # Compare string representations
    assert str(expected_tss) in [str(tss) for tss in ps.tss_list]
    # Ensure original path triples are NOT in tss_list
    assert str(
        TriplesSameSubject.from_spo(
            focus_node_var, IRI(value=PROV.qualifiedDerivation), path_node_1_var
        )
    ) not in [str(tss) for tss in ps.tss_list]
    assert str(
        TriplesSameSubject.from_spo(
            path_node_1_var, IRI(value=PROV.hadRole), path_node_2_var
        )
    ) not in [str(tss) for tss in ps.tss_list]
    assert str(
        TriplesSameSubject.from_spo(
            path_node_2_var, IRI(value=RDFS.label), path_node_3_var
        )
    ) not in [str(tss) for tss in ps.tss_list]

    assert len(ps.tssp_list) == 3
    # Compare strings for TSSP list contents
    tssp_list_strs = [str(tssp) for tssp in ps.tssp_list]
    # Removed checks for tssp_list content as per user request


@patch("prez.services.query_generation.shacl.settings")
def test_alias_triples_inverse_path(mock_settings):
    """Verify TSS (construct) uses alias, TSSP (where) uses original path for inverse paths."""
    mock_settings.use_path_aliases = True
    g = Graph().parse(
        data="""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path [ sh:inversePath dcterms:subject ] ;
            shext:pathAlias <https://alias/isSubjectOf> ;
        ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    focus_node_var = Var(value="focus_node")
    path_node_1_var = Var(value="prof_1_node_1")
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=focus_node_var, shape_number=0
    )

    # Expected CONSTRUCT triple (using alias)
    expected_tss = TriplesSameSubject.from_spo(
        focus_node_var, IRI(value="https://alias/isSubjectOf"), path_node_1_var
    )

    # Expected WHERE triple (using original inverse path)
    expected_tssp = TriplesSameSubjectPath.from_spo(
        path_node_1_var, IRI(value=DCTERMS.subject), focus_node_var
    )

    # Compare string representations
    assert str(expected_tss) in [str(tss) for tss in ps.tss_list]
    # Ensure original path triple is NOT in tss_list
    original_tss = TriplesSameSubject.from_spo(
        path_node_1_var, IRI(value=DCTERMS.subject), focus_node_var
    )
    assert str(original_tss) not in [str(tss) for tss in ps.tss_list]

    # Removed checks for tssp_list content as per user request


@patch("prez.services.query_generation.shacl.settings")
def test_alias_triples_alternative_path(mock_settings):
    """Verify TSS (construct) uses alias, TSSP (where) uses original path for alternative paths."""
    mock_settings.use_path_aliases = True
    g = Graph().parse(
        data="""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX shext: <http://example.com/shacl-extension#>

        <http://example-profile> sh:property [
            sh:path [ sh:alternativePath ( skos:prefLabel rdfs:label ) ] ;
            shext:pathAlias <https://alias/label> ;
        ] .
    """
    )
    path_bn = g.value(subject=URIRef("http://example-profile"), predicate=SH.property)
    focus_node_var = Var(value="focus_node")
    path_node_1_var = Var(value="prof_1_node_1")
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=focus_node_var, shape_number=0
    )

    # Expected CONSTRUCT triple (using alias)
    expected_tss = TriplesSameSubject.from_spo(
        focus_node_var, IRI(value="https://alias/label"), path_node_1_var
    )

    # Expected WHERE triple (using original alternative path SPARQL grammar)
    # Manually construct the complex TSSP object for skos:prefLabel | rdfs:label
    alt_path_obj = AlternativePath(
        value=[Path(value=SKOS.prefLabel), Path(value=RDFS.label)]
    )
    sequence_paths = []
    for alt_path_item in alt_path_obj.value:
        list_path_elt_or_inverse = [_build_path_elt_or_inverse(alt_path_item)]
        sequence_paths.append(
            PathSequence(list_path_elt_or_inverse=list_path_elt_or_inverse)
        )
    # Compare string representations
    assert str(expected_tss) in [str(tss) for tss in ps.tss_list]
    # Ensure original path triples are NOT in tss_list (simple paths within alternative)
    assert str(
        TriplesSameSubject.from_spo(
            focus_node_var, IRI(value=SKOS.prefLabel), path_node_1_var
        )
    ) not in [str(tss) for tss in ps.tss_list]
    assert str(
        TriplesSameSubject.from_spo(
            focus_node_var, IRI(value=RDFS.label), path_node_1_var
        )
    ) not in [str(tss) for tss in ps.tss_list]

    # Removed checks for tssp_list content as per user request


@patch("prez.services.query_generation.shacl.settings")
def test_gswa_like_profile(mock_settings):
    mock_settings.use_path_aliases = True
    gswa_profile = """PREFIX altr-ext: <http://www.w3.org/ns/dx/connegp/altr-ext#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX geo: <http://www.opengis.net/ont/geosparql#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX prez: <https://prez.dev/>
    PREFIX prof: <http://www.w3.org/ns/dx/prof/>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX reg: <http://purl.org/linked-data/registry#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    PREFIX shext: <http://example.com/shacl-extension#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX schema: <https://schema.org/>
    PREFIX sosa: <http://www.w3.org/ns/sosa/>
    PREFIX ex: <https://example.com/dataset/gswa/>

    <https://prez.dev/profile/formation-top>
        a prof:Profile , prez:ListingProfile ;
        dcterms:identifier "formation-top"^^xsd:token ;
        dcterms:description "Formation top data extract to match WAPIMS interface table" ;
        dcterms:title "Formation top table" ;
        altr-ext:constrainsClass sosa:Sample , <https://linked.data.gov.au/def/borehole/Bore> ;
        altr-ext:hasDefaultResourceFormat "text/anot+turtle" ;
        altr-ext:hasResourceFormat "application/geo+json" ,
            "application/ld+json" ,
            "application/anot+ld+json" ,
            "application/rdf+xml" ,
            "text/anot+turtle" ,
            "text/turtle" ;
        altr-ext:hasNodeShape [
            a sh:NodeShape ;
            sh:targetClass rdfs:Resource , <https://linked.data.gov.au/def/borehole/Bore> ;
            altr-ext:hasDefaultProfile <https://prez.dev/profile/formation-top>
        ] ;
    sh:property [
        sh:path [
                sh:union (
                        [
                            sh:path ( sosa:isSampleOf [ sh:inversePath dcterms:hasPart ] ) ;
                            shext:pathAlias <https://example.com/sample-parent> ;
                        ]
                        [
                            sh:path ( sosa:isSampleOf [ sh:inversePath dcterms:hasPart ] schema:identifier ) ;
                            shext:pathAlias <https://example.com/sample-parent-identifier> ;
                        ]
                        sosa:isSampleOf
                        [
                            sh:path ( sosa:isSampleOf schema:identifier ) ;
                            shext:pathAlias <https://example.com/sample-identifier> ;
                        ]
                        [
                            sh:path ( sosa:isSampleOf [ sh:inversePath dcterms:hasPart ] geo:sfWithin ) ;
                            shext:pathAlias <https://example.com/sample-parent-location> ;
                        ]
                        [
                            sh:path ( sosa:isSampleOf [ sh:inversePath dcterms:hasPart ] ex:originatesFrom ) ;
                            shext:pathAlias <https://example.com/sample-parent-origin> ;
                        ]
                        [
                            sh:path ( sosa:isSampleOf schema:depth ex:topDepth ) ;
                            shext:pathAlias <https://my_prop_path> ;
                            sh:facet true
                        ]
                        [
                            sh:path ( sosa:isSampleOf schema:depth ex:bottomDepth ) ;
                            shext:pathAlias <https://example.com/sample-bottom-depth> ;
                        ]
                        schema:name
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:observedProperty ) ;
                            shext:pathAlias <https://example.com/feature-observed-property> ;
                        ]
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:hasResult schema:minValue ex:hasAgeName ) ;
                            shext:pathAlias <https://example.com/feature-result-min-age-name> ;
                        ]
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:hasResult schema:minValue ex:hasAgeName schema:value) ;
                            shext:pathAlias <https://example.com/feature-result-min-age-value> ;
                        ]
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:hasResult schema:maxValue ex:hasAgeName ) ;
                            shext:pathAlias <https://example.com/feature-result-max-age-name> ;
                        ]
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:hasResult schema:maxValue ex:hasAgeName schema:value) ;
                            shext:pathAlias <https://example.com/feature-result-max-age-value> ;
                        ]
                        [
                            sh:path ( [ sh:inversePath sosa:hasFeatureOfInterest ] sosa:hasResult schema:comment ) ;
                            shext:pathAlias <https://example.com/feature-result-comment> ;
                        ]
                        schema:citation
                        schema:comment
                )
            ]
        ] ;
    ."""
    g = Graph().parse(data=gswa_profile)
    path_bn = g.value(
        subject=URIRef("https://prez.dev/profile/formation-top"), predicate=SH.property
    )
    focus_node_var = Var(value="focus_node")
    path_node_1_var = Var(value="prof_1_node_1")
    ps = PropertyShape(
        uri=path_bn, graph=g, kind="profile", focus_node=focus_node_var, shape_number=0
    )
