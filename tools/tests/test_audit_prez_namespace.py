from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph

from tools.audit_prez_namespace import (
    namespace_bucket,
    scan_roots,
    textual_iri_occurrences,
    write_csv,
    write_markdown,
    write_turtle,
)


def test_text_scanner_resolves_prefixes_and_python_namespaces():
    text = """
        @prefix prez: <https://prez.dev/> .
        PREFIX ont: <https://prez.dev/ont/>
        prez:Manifest ont:endpointTemplate "x" .

        PREZ = Namespace("https://prez.dev/")
        first = PREZ.label
        second = PREZ["description"]
    """

    occurrences = textual_iri_occurrences(text)

    assert occurrences["https://prez.dev/Manifest"] == 1
    assert occurrences["https://prez.dev/ont/endpointTemplate"] == 1
    assert occurrences["https://prez.dev/label"] == 1
    assert occurrences["https://prez.dev/description"] == 1
    assert "https://prez.dev/" not in occurrences


def test_text_scanner_rejects_delimiter_noise_and_lowercase_namespace_collisions():
    text = """
        value = "https://prez.dev/ont/ListingEndpoint'"
        link = "https://prez.dev/profile/facet-by-type&_mediatype=text/turtle"
        prez = Namespace("https://prez.dev/")
        import prez.cache
    """

    occurrences = textual_iri_occurrences(text)

    assert occurrences["https://prez.dev/ont/ListingEndpoint"] == 1
    assert occurrences["https://prez.dev/profile/facet-by-type"] == 1
    assert "https://prez.dev/cache" not in occurrences


def test_scan_and_write_inventory(tmp_path: Path):
    group = tmp_path / "Kurrawong"
    repository = group / "example"
    (repository / ".git").mkdir(parents=True)
    source = repository / "data.ttl"
    source.write_text(
        """@prefix prez: <https://prez.dev/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

prez:Manifest a owl:Class ;
    rdfs:label "Manifest" ;
    rdfs:comment "A test manifest." .

[] prez:sync false .
""",
        encoding="utf-8",
    )
    tests_directory = repository / "tests"
    tests_directory.mkdir()
    (tests_directory / "test_usage.py").write_text(
        'SYNC = "https://prez.dev/sync"\n', encoding="utf-8"
    )
    (repository / "named-graph.trig").write_text(
        """@prefix prez: <https://prez.dev/> .
<urn:graph> { [] prez:link </item> . }
""",
        encoding="utf-8",
    )

    result = scan_roots({"Kurrawong": group})

    manifest = result.observations["https://prez.dev/Manifest"]
    sync = result.observations["https://prez.dev/sync"]
    link = result.observations["https://prez.dev/link"]
    assert manifest.definition_status == "typed"
    assert manifest.inferred_kind == "class"
    assert manifest.labels == {"Manifest"}
    assert manifest.descriptions == {"A test manifest."}
    assert sync.inferred_kind == "property candidate"
    assert len(sync.category_files["production"]) == 1
    assert len(sync.category_files["test"]) == 1
    assert link.inferred_kind == "property candidate"
    assert (
        namespace_bucket("https://prez.dev/ont/endpointTemplate")
        == "configuration ontology"
    )

    output = tmp_path / "output"
    generated_at = datetime(2026, 10, 5, tzinfo=timezone.utc).isoformat()
    write_csv(result, output / "inventory.csv")
    write_markdown(
        result,
        output / "audit.md",
        generated_at,
        "python tools/audit_prez_namespace.py",
    )
    write_turtle(result, output / "inventory.ttl", generated_at)

    assert "https://prez.dev/Manifest" in (output / "inventory.csv").read_text()
    assert "Priority definition gaps" in (output / "audit.md").read_text()
    Graph().parse(output / "inventory.ttl", format="turtle")


def test_scan_excludes_generated_output_directory(tmp_path: Path):
    group = tmp_path / "Kurrawong"
    repository = group / "example"
    (repository / ".git").mkdir(parents=True)
    output = repository / "docs" / "namespace-audit"
    output.mkdir(parents=True)
    (output / "previous.csv").write_text(
        "https://prez.dev/ShouldNotBeRescanned\n", encoding="utf-8"
    )
    (repository / "source.py").write_text(
        'IRI = "https://prez.dev/ShouldBeScanned"\n', encoding="utf-8"
    )

    result = scan_roots({"Kurrawong": group}, excluded_paths={output})

    assert "https://prez.dev/ShouldBeScanned" in result.observations
    assert "https://prez.dev/ShouldNotBeRescanned" not in result.observations
