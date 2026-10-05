#!/usr/bin/env python3
"""Inventory Prez namespace usage across groups of Git repositories.

The scanner combines a tolerant text scan with RDF parsing. Text scanning finds
terms embedded in source code and documentation; RDF parsing adds evidence about
whether a term occurs as a subject, predicate, object, class, or declared
resource. Parse failures do not discard the text evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD


PREZ_BASE = "https://prez.dev/"
AUDIT = Namespace("urn:prez-namespace-audit:vocab/")
PROF_PROFILE = URIRef("http://www.w3.org/ns/dx/prof/Profile")
SCHEMA_NAME = URIRef("https://schema.org/name")
SCHEMA_DESCRIPTION = URIRef("https://schema.org/description")

EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".output",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "target",
    "venv",
}

TEXT_SUFFIXES = {
    ".cfg",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonld",
    ".jsx",
    ".md",
    ".n3",
    ".nq",
    ".nt",
    ".owl",
    ".py",
    ".rdf",
    ".rq",
    ".rst",
    ".sh",
    ".sparql",
    ".toml",
    ".trig",
    ".ts",
    ".tsx",
    ".ttl",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}

TEXT_FILENAMES = {
    "Dockerfile",
    "Justfile",
    "Makefile",
    "Taskfile",
}

RDF_FORMATS = {
    ".jsonld": "json-ld",
    ".n3": "n3",
    ".nq": "nquads",
    ".nt": "nt",
    ".owl": "xml",
    ".rdf": "xml",
    ".trig": "trig",
    ".ttl": "turtle",
}

FULL_IRI_PATTERN = re.compile(r"https://prez\.dev/[A-Za-z0-9._~!$'()*+,;=:@%/?#&/-]+")
PREFIX_PATTERN = re.compile(
    r"(?im)(?:@prefix|prefix)\s+([A-Za-z_][\w-]*|):\s*"
    r"<(?P<base>https://prez\.dev/[^>\s]*)>"
)
PYTHON_NAMESPACE_PATTERN = re.compile(
    r"(?m)^\s*([A-Z][A-Z0-9_]*)\s*=\s*Namespace\("
    r"[\"'](?P<base>https://prez\.dev/[^\"']*)[\"']\)"
)

LABEL_PREDICATES = {
    RDFS.label,
    SKOS.prefLabel,
    DCTERMS.title,
    SCHEMA_NAME,
}
DESCRIPTION_PREDICATES = {
    RDFS.comment,
    SKOS.definition,
    DCTERMS.description,
    SCHEMA_DESCRIPTION,
}

CLASS_TYPES = {OWL.Class, RDFS.Class}
PROPERTY_TYPES = {
    RDF.Property,
    OWL.AnnotationProperty,
    OWL.DatatypeProperty,
    OWL.ObjectProperty,
}

CATEGORY_ORDER = ("production", "test", "example", "documentation", "generated")


@dataclass(frozen=True)
class Repository:
    group: str
    name: str
    path: Path

    @property
    def key(self) -> str:
        return f"{self.group}/{self.name}"


@dataclass
class ParseFailure:
    source: str
    message: str


@dataclass
class ScanStatistics:
    repositories: int = 0
    files_scanned: int = 0
    rdf_files_parsed: int = 0
    files_skipped_as_large: int = 0
    files_skipped_as_binary: int = 0
    parse_failures: list[ParseFailure] = field(default_factory=list)


@dataclass
class TermObservation:
    iri: str
    textual_occurrences: int = 0
    source_files: set[str] = field(default_factory=set)
    repositories: set[str] = field(default_factory=set)
    category_files: dict[str, set[str]] = field(
        default_factory=lambda: {category: set() for category in CATEGORY_ORDER}
    )
    rdf_roles: Counter[str] = field(default_factory=Counter)
    declared_types: set[str] = field(default_factory=set)
    labels: set[str] = field(default_factory=set)
    descriptions: set[str] = field(default_factory=set)

    def add_source(
        self,
        source: str,
        repository: str,
        category: str,
        occurrences: int = 0,
    ) -> None:
        self.textual_occurrences += occurrences
        self.source_files.add(source)
        self.repositories.add(repository)
        self.category_files[category].add(source)

    @property
    def definition_status(self) -> str:
        if self.declared_types:
            return "typed"
        if self.descriptions:
            return "described"
        if self.labels:
            return "labelled"
        return "observed"

    @property
    def inferred_kind(self) -> str:
        types = {URIRef(value) for value in self.declared_types}
        kinds: list[str] = []
        if types & CLASS_TYPES:
            kinds.append("class")
        if types & PROPERTY_TYPES:
            kinds.append("property")
        if PROF_PROFILE in types:
            kinds.append("profile")
        if SH.NodeShape in types:
            kinds.append("node shape")
        if SKOS.Concept in types:
            kinds.append("concept")
        if OWL.Ontology in types:
            kinds.append("ontology")
        if not kinds and self.rdf_roles["predicate"]:
            kinds.append("property candidate")
        if not kinds and self.rdf_roles["type_object"]:
            kinds.append("class candidate")
        if not kinds:
            kinds.append("resource")
        return "; ".join(kinds)


@dataclass
class AuditResult:
    roots: dict[str, Path]
    observations: dict[str, TermObservation]
    statistics: ScanStatistics


def normalize_prez_iri(value: str) -> str | None:
    """Return a vocabulary-like Prez IRI, excluding bare namespace bases."""
    value = value.rstrip(".,;:!?)]}'\"")
    value = value.split("?", 1)[0].split("#", 1)[0].split("&", 1)[0]
    if not value.startswith(PREZ_BASE) or value.endswith("/"):
        return None
    if value == PREZ_BASE.rstrip("/"):
        return None
    return value


def namespace_bucket(iri: str) -> str:
    remainder = iri.removeprefix(PREZ_BASE)
    buckets = (
        ("ont/", "configuration ontology"),
        ("profile/", "profile identifier"),
        ("endpoint/", "endpoint identifier"),
        ("ManifestResourceRoles/", "manifest resource roles"),
        ("ManifestVersionTypes/", "manifest version types"),
        ("jena-lucene/", "Jena Lucene configuration"),
        ("kgmanifest/", "KG Manifest documentation"),
    )
    for prefix, bucket in buckets:
        if remainder.startswith(prefix):
            return bucket
    if "/" not in remainder:
        return "root namespace"
    return "other Prez path"


def local_name(iri: str) -> str:
    return iri.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def source_category(relative_path: Path) -> str:
    lower_parts = [part.lower() for part in relative_path.parts]
    lower_name = relative_path.name.lower()
    joined = "/".join(lower_parts)
    if (
        "/public/export/" in f"/{joined}/"
        or "generated" in lower_parts
        or "output" in lower_parts
        or lower_name.endswith((".min.js", ".min.css"))
    ):
        return "generated"
    if any(
        part in {"test", "tests", "test_data"} for part in lower_parts
    ) or lower_name.startswith("test_"):
        return "test"
    if any(
        part in {"demo", "demos", "example", "examples", "fixture", "fixtures"}
        for part in lower_parts
    ):
        return "example"
    if "docs" in lower_parts or relative_path.suffix.lower() in {".md", ".rst"}:
        return "documentation"
    return "production"


def discover_repositories(roots: dict[str, Path]) -> list[Repository]:
    repositories: list[Repository] = []
    for group, root in sorted(roots.items()):
        if not root.exists():
            raise FileNotFoundError(f"Scan root does not exist: {root}")
        if (root / ".git").exists():
            repositories.append(Repository(group, root.name, root))
            continue
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / ".git").exists():
                repositories.append(Repository(group, child.name, child))
    return repositories


def iter_source_files(
    repository: Repository, excluded_paths: set[Path] | None = None
) -> Iterable[Path]:
    excluded_paths = {path.resolve() for path in (excluded_paths or set())}
    for current_root, directories, filenames in os.walk(repository.path):
        current = Path(current_root)
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in EXCLUDED_DIRECTORIES
            and not any(
                (current / directory).resolve() == excluded
                or (current / directory).resolve().is_relative_to(excluded)
                for excluded in excluded_paths
            )
        )
        for filename in sorted(filenames):
            path = current / filename
            if any(
                path.resolve() == excluded or path.resolve().is_relative_to(excluded)
                for excluded in excluded_paths
            ):
                continue
            if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_FILENAMES:
                yield path


def compact_iri_occurrences(text: str) -> Counter[str]:
    occurrences: Counter[str] = Counter()
    for match in PREFIX_PATTERN.finditer(text):
        prefix = match.group(1)
        base = match.group("base")
        if not base.endswith(("/", "#")):
            continue
        token_pattern = re.compile(
            rf"(?<![\w/]){re.escape(prefix)}:([A-Za-z_][A-Za-z0-9._~/-]*)"
        )
        for token_match in token_pattern.finditer(text):
            iri = normalize_prez_iri(base + token_match.group(1))
            if iri:
                occurrences[iri] += 1
    return occurrences


def python_namespace_occurrences(text: str) -> Counter[str]:
    occurrences: Counter[str] = Counter()
    for match in PYTHON_NAMESPACE_PATTERN.finditer(text):
        variable = match.group(1)
        base = match.group("base")
        dot_pattern = re.compile(rf"\b{re.escape(variable)}\.([A-Za-z_][A-Za-z0-9_]*)")
        item_pattern = re.compile(rf"\b{re.escape(variable)}\[[\"']([^\"']+)[\"']\]")
        for token_match in dot_pattern.finditer(text):
            iri = normalize_prez_iri(base + token_match.group(1))
            if iri:
                occurrences[iri] += 1
        for token_match in item_pattern.finditer(text):
            iri = normalize_prez_iri(base + token_match.group(1))
            if iri:
                occurrences[iri] += 1
    return occurrences


def textual_iri_occurrences(text: str) -> Counter[str]:
    occurrences: Counter[str] = Counter()
    for match in FULL_IRI_PATTERN.finditer(text):
        iri = normalize_prez_iri(match.group(0))
        if iri:
            occurrences[iri] += 1
    occurrences.update(compact_iri_occurrences(text))
    occurrences.update(python_namespace_occurrences(text))
    return occurrences


def clean_literal(value: object, maximum_length: int = 240) -> str:
    cleaned = " ".join(str(value).split())
    if len(cleaned) > maximum_length:
        return cleaned[: maximum_length - 1] + "…"
    return cleaned


def get_observation(
    observations: dict[str, TermObservation], iri: str
) -> TermObservation:
    return observations.setdefault(iri, TermObservation(iri=iri))


def record_rdf_evidence(
    graph: Graph,
    observations: dict[str, TermObservation],
    source: str,
    repository: str,
    category: str,
) -> None:
    for statement in graph:
        subject, predicate, obj = statement[:3]
        terms = (("subject", subject), ("predicate", predicate), ("object", obj))
        for role, term in terms:
            if not isinstance(term, URIRef):
                continue
            iri = normalize_prez_iri(str(term))
            if not iri:
                continue
            observation = get_observation(observations, iri)
            observation.add_source(source, repository, category)
            observation.rdf_roles[role] += 1
            if role == "object" and predicate == RDF.type:
                observation.rdf_roles["type_object"] += 1

        if isinstance(subject, URIRef):
            subject_iri = normalize_prez_iri(str(subject))
            if subject_iri:
                observation = get_observation(observations, subject_iri)
                if predicate == RDF.type and isinstance(obj, URIRef):
                    observation.declared_types.add(str(obj))
                elif predicate in LABEL_PREDICATES and isinstance(obj, Literal):
                    observation.labels.add(clean_literal(obj))
                elif predicate in DESCRIPTION_PREDICATES and isinstance(obj, Literal):
                    observation.descriptions.add(clean_literal(obj))


def scan_roots(
    roots: dict[str, Path],
    maximum_file_bytes: int = 5_000_000,
    excluded_paths: set[Path] | None = None,
) -> AuditResult:
    observations: dict[str, TermObservation] = {}
    statistics = ScanStatistics()
    repositories = discover_repositories(roots)
    statistics.repositories = len(repositories)

    for repository in repositories:
        for path in iter_source_files(repository, excluded_paths=excluded_paths):
            try:
                if path.stat().st_size > maximum_file_bytes:
                    statistics.files_skipped_as_large += 1
                    continue
                raw = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in raw:
                statistics.files_skipped_as_binary += 1
                continue
            text = raw.decode("utf-8", errors="replace")
            statistics.files_scanned += 1
            relative_path = path.relative_to(repository.path)
            source = f"{repository.key}/{relative_path.as_posix()}"
            category = source_category(relative_path)

            for iri, count in textual_iri_occurrences(text).items():
                observation = get_observation(observations, iri)
                observation.add_source(source, repository.key, category, count)

            rdf_format = RDF_FORMATS.get(path.suffix.lower())
            if (
                path.suffix.lower() == ".xml"
                and "<rdf:RDF" in text[:10_000]
                and "http://www.w3.org/1999/02/22-rdf-syntax-ns#" in text[:10_000]
            ):
                rdf_format = "xml"
            if not rdf_format:
                continue
            graph = Dataset(default_union=True)
            try:
                graph.parse(data=text, format=rdf_format, publicID=path.as_uri())
            except Exception as error:  # RDF parsers expose several exception types.
                statistics.parse_failures.append(
                    ParseFailure(source=source, message=clean_literal(error))
                )
                continue
            statistics.rdf_files_parsed += 1
            record_rdf_evidence(
                graph,
                observations,
                source,
                repository.key,
                category,
            )

    return AuditResult(roots=roots, observations=observations, statistics=statistics)


CSV_FIELDS = (
    "iri",
    "namespace_bucket",
    "local_name",
    "inferred_kind",
    "definition_status",
    "textual_occurrences",
    "source_files",
    "repositories",
    "production_files",
    "test_files",
    "example_files",
    "documentation_files",
    "generated_files",
    "rdf_subject_uses",
    "rdf_predicate_uses",
    "rdf_object_uses",
    "rdf_type_object_uses",
    "declared_types",
    "observed_labels",
    "observed_descriptions",
    "sample_sources",
)


def observation_row(observation: TermObservation) -> dict[str, object]:
    return {
        "iri": observation.iri,
        "namespace_bucket": namespace_bucket(observation.iri),
        "local_name": local_name(observation.iri),
        "inferred_kind": observation.inferred_kind,
        "definition_status": observation.definition_status,
        "textual_occurrences": observation.textual_occurrences,
        "source_files": len(observation.source_files),
        "repositories": len(observation.repositories),
        "production_files": len(observation.category_files["production"]),
        "test_files": len(observation.category_files["test"]),
        "example_files": len(observation.category_files["example"]),
        "documentation_files": len(observation.category_files["documentation"]),
        "generated_files": len(observation.category_files["generated"]),
        "rdf_subject_uses": observation.rdf_roles["subject"],
        "rdf_predicate_uses": observation.rdf_roles["predicate"],
        "rdf_object_uses": observation.rdf_roles["object"],
        "rdf_type_object_uses": observation.rdf_roles["type_object"],
        "declared_types": " | ".join(sorted(observation.declared_types)),
        "observed_labels": " | ".join(sorted(observation.labels)),
        "observed_descriptions": " | ".join(sorted(observation.descriptions)),
        "sample_sources": " | ".join(sorted(observation.source_files)[:5]),
    }


def write_csv(result: AuditResult, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for iri in sorted(result.observations):
            writer.writerow(observation_row(result.observations[iri]))


def count_by(observations: Iterable[TermObservation], value_getter) -> Counter[str]:
    return Counter(value_getter(observation) for observation in observations)


def markdown_table(headers: tuple[str, ...], rows: Iterable[tuple[object, ...]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = [str(value).replace("|", "\\|").replace("\n", " ") for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_markdown(
    result: AuditResult,
    destination: Path,
    generated_at: str,
    command: str,
) -> None:
    observations = list(result.observations.values())
    status_counts = count_by(observations, lambda item: item.definition_status)
    bucket_counts = count_by(observations, lambda item: namespace_bucket(item.iri))
    repository_counts: Counter[str] = Counter()
    for observation in observations:
        repository_counts.update(observation.repositories)

    priority_gaps = sorted(
        (
            observation
            for observation in observations
            if observation.definition_status == "observed"
            and observation.category_files["production"]
        ),
        key=lambda item: (
            -len(item.category_files["production"]),
            -len(item.repositories),
            item.iri,
        ),
    )

    lines = [
        "# Prez namespace audit",
        "",
        f"Generated at `{generated_at}` by `tools/audit_prez_namespace.py`.",
        "",
        "This is an evidence inventory, not a canonical ontology. It records observed Prez IRIs and separates textual occurrences from RDF-role evidence. A term being observed, labelled, or typed does not by itself make its semantics normative.",
        "",
        "## Scope",
        "",
        markdown_table(
            ("Group", "Scan root"),
            ((group, f"`{root}`") for group, root in sorted(result.roots.items())),
        ),
        "",
        f"The scan inspected **{result.statistics.files_scanned:,} files** in **{result.statistics.repositories:,} Git repositories**, parsed **{result.statistics.rdf_files_parsed:,} RDF files**, and observed **{len(observations):,} distinct Prez IRIs**.",
        "",
        "Excluded directories include `.git`, dependency trees, virtual environments, caches, build outputs, and coverage outputs. Remaining files are classified as production, test, example, documentation, or generated evidence. The scanner is deliberately tolerant: RDF parse failures retain text evidence but cannot contribute RDF-role evidence.",
        "",
        "## Reproduce",
        "",
        "```shell",
        command,
        "```",
        "",
        "## Definition status",
        "",
        "Statuses are evidence levels: `observed` means usage only; `labelled` adds a recognised label; `described` adds a recognised description; and `typed` means the term is the subject of at least one `rdf:type` statement. `typed` does not imply that the type or semantics are correct.",
        "",
        markdown_table(
            ("Status", "Terms"),
            (
                (status, status_counts[status])
                for status in ("typed", "described", "labelled", "observed")
            ),
        ),
        "",
        "## Namespace areas",
        "",
        markdown_table(
            ("Area", "Terms"),
            sorted(bucket_counts.items(), key=lambda item: (-item[1], item[0])),
        ),
        "",
        "## Repository footprint",
        "",
        "The count below is the number of distinct observed terms associated with each repository, not the number of occurrences.",
        "",
        markdown_table(
            ("Repository", "Distinct terms"),
            sorted(repository_counts.items(), key=lambda item: (-item[1], item[0])),
        ),
        "",
        "## Priority definition gaps",
        "",
        "These terms occur in files classified as production but have no recognised RDF type, label, or description in the scanned RDF. They are candidates for review, not automatic ontology additions.",
        "",
        markdown_table(
            ("IRI", "Kind evidence", "Production files", "Repositories", "All files"),
            (
                (
                    f"<{item.iri}>",
                    item.inferred_kind,
                    len(item.category_files["production"]),
                    len(item.repositories),
                    len(item.source_files),
                )
                for item in priority_gaps[:50]
            ),
        ),
        "",
        "## Complete inventory",
        "",
        markdown_table(
            (
                "IRI",
                "Area",
                "Kind evidence",
                "Status",
                "Files",
                "Repos",
                "Prod",
                "Test",
                "Example",
                "Docs",
                "Generated",
            ),
            (
                (
                    f"<{item.iri}>",
                    namespace_bucket(item.iri),
                    item.inferred_kind,
                    item.definition_status,
                    len(item.source_files),
                    len(item.repositories),
                    len(item.category_files["production"]),
                    len(item.category_files["test"]),
                    len(item.category_files["example"]),
                    len(item.category_files["documentation"]),
                    len(item.category_files["generated"]),
                )
                for item in sorted(observations, key=lambda item: item.iri)
            ),
        ),
        "",
        "## RDF parse failures",
        "",
        f"There were **{len(result.statistics.parse_failures):,} RDF parse failures**, **{result.statistics.files_skipped_as_large:,} files skipped for size**, and **{result.statistics.files_skipped_as_binary:,} binary files skipped**.",
        "",
    ]
    if result.statistics.parse_failures:
        lines.extend(
            [
                "The first 50 parse failures are shown below. The corresponding files still contributed text evidence.",
                "",
                markdown_table(
                    ("Source", "Parser message"),
                    (
                        (f"`{failure.source}`", failure.message)
                        for failure in result.statistics.parse_failures[:50]
                    ),
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation cautions",
            "",
            "- A URL under `prez.dev` may identify documentation, a profile, a graph, an endpoint, a controlled-vocabulary concept, or an ontology term.",
            "- `property candidate` means the IRI appeared in predicate position; `class candidate` means it appeared as the object of `rdf:type`. Neither is a proposed formal declaration.",
            "- Counts are affected by cloned fixtures and generated exports. Category columns make those sources visible rather than silently discarding them.",
            "- Compact IRIs are resolved from in-file `PREFIX` or `@prefix` declarations. Python `rdflib.Namespace` attribute and item access is also recognised. Other dynamically constructed IRIs may require a future language-specific extractor.",
            "- The Turtle output uses a private `urn:prez-namespace-audit:vocab/` reporting vocabulary so the audit does not mint additional public Prez terms.",
            "",
        ]
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def add_integer(graph: Graph, subject: URIRef, predicate: URIRef, value: int) -> None:
    graph.add((subject, predicate, Literal(value, datatype=XSD.integer)))


def write_turtle(
    result: AuditResult,
    destination: Path,
    generated_at: str,
) -> None:
    graph = Graph()
    graph.bind("audit", AUDIT)
    graph.bind("dcterms", DCTERMS)
    graph.bind("rdf", RDF)
    graph.bind("xsd", XSD)
    report = AUDIT.report
    graph.add((report, RDF.type, AUDIT.NamespaceAudit))
    graph.add((report, DCTERMS.title, Literal("Prez namespace audit")))
    graph.add(
        (
            report,
            DCTERMS.created,
            Literal(generated_at, datatype=XSD.dateTime),
        )
    )
    add_integer(graph, report, AUDIT.repositoryCount, result.statistics.repositories)
    add_integer(graph, report, AUDIT.fileCount, result.statistics.files_scanned)
    add_integer(graph, report, AUDIT.termCount, len(result.observations))

    for iri, observation in sorted(result.observations.items()):
        digest = hashlib.sha256(iri.encode("utf-8")).hexdigest()[:20]
        node = URIRef(f"urn:prez-namespace-audit:term:{digest}")
        graph.add((report, AUDIT.hasObservation, node))
        graph.add((node, RDF.type, AUDIT.TermObservation))
        graph.add((node, AUDIT["term"], URIRef(iri)))
        graph.add((node, AUDIT.namespaceBucket, Literal(namespace_bucket(iri))))
        graph.add((node, AUDIT.localName, Literal(local_name(iri))))
        graph.add((node, AUDIT.inferredKind, Literal(observation.inferred_kind)))
        graph.add(
            (node, AUDIT.definitionStatus, Literal(observation.definition_status))
        )
        add_integer(
            graph, node, AUDIT.textualOccurrenceCount, observation.textual_occurrences
        )
        add_integer(graph, node, AUDIT.sourceFileCount, len(observation.source_files))
        add_integer(graph, node, AUDIT.repositoryCount, len(observation.repositories))
        for category in CATEGORY_ORDER:
            predicate = AUDIT[f"{category}FileCount"]
            add_integer(
                graph, node, predicate, len(observation.category_files[category])
            )
        for role in ("subject", "predicate", "object", "type_object"):
            predicate = AUDIT[f"rdf{role.title().replace('_', '')}UseCount"]
            add_integer(graph, node, predicate, observation.rdf_roles[role])
        for declared_type in sorted(observation.declared_types):
            graph.add((node, AUDIT.declaredType, URIRef(declared_type)))
        for label in sorted(observation.labels):
            graph.add((node, AUDIT.observedLabel, Literal(label)))
        for description in sorted(observation.descriptions):
            graph.add((node, AUDIT.observedDescription, Literal(description)))
        for source in sorted(observation.source_files)[:5]:
            graph.add((node, AUDIT.sampleSource, Literal(source)))

    destination.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=destination, format="turtle")


def parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("roots must use LABEL=/absolute/path")
    label, raw_path = value.split("=", 1)
    if not label or not raw_path:
        raise argparse.ArgumentTypeError("roots must use LABEL=/absolute/path")
    path = Path(raw_path).expanduser().resolve()
    return label, path


def default_roots(projects_directory: Path) -> dict[str, Path]:
    return {
        group: (projects_directory / group).resolve()
        for group in ("Kurrawong", "IDN", "BDR")
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        action="append",
        type=parse_root,
        metavar="LABEL=PATH",
        help="scan root; repeat for multiple repository groups",
    )
    parser.add_argument(
        "--projects-directory",
        type=Path,
        default=Path.home() / "Projects",
        help="parent of Kurrawong, IDN, and BDR when --root is omitted",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("docs/namespace-audit"),
    )
    parser.add_argument(
        "--maximum-file-bytes",
        type=int,
        default=5_000_000,
    )
    parser.add_argument(
        "--generated-at",
        help="ISO timestamp override, useful for deterministic tests",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.getLogger("rdflib").setLevel(logging.CRITICAL)
    roots = dict(args.root) if args.root else default_roots(args.projects_directory)
    output_directory = args.output_directory.resolve()
    tool_directory = Path(__file__).resolve().parent
    generated_at = (
        args.generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )
    result = scan_roots(
        roots,
        maximum_file_bytes=args.maximum_file_bytes,
        excluded_paths={
            output_directory,
            Path(__file__).resolve(),
            tool_directory / "tests",
        },
    )

    write_csv(result, output_directory / "prez-namespace-inventory.csv")
    command_roots = " ".join(
        f"--root {label}={path}" for label, path in sorted(roots.items())
    )
    command = (
        "poetry run python tools/audit_prez_namespace.py \\\n"
        f"  {command_roots} \\\n"
        f"  --output-directory {args.output_directory}"
    )
    write_markdown(
        result,
        output_directory / "prez-namespace-audit.md",
        generated_at,
        command,
    )
    write_turtle(
        result,
        output_directory / "prez-namespace-inventory.ttl",
        generated_at,
    )
    print(
        f"Observed {len(result.observations)} Prez IRIs in "
        f"{result.statistics.files_scanned} files across "
        f"{result.statistics.repositories} repositories."
    )
    print(f"Wrote audit artifacts to {output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
