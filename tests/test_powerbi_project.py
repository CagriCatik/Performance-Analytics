from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POWERBI = ROOT / "powerbi"
MODEL = POWERBI / "PerformanceAnalytics.SemanticModel" / "definition"
REPORT = POWERBI / "PerformanceAnalytics.Report" / "definition"


def test_pbip_artifact_graph_is_complete() -> None:
    pbip = json.loads((POWERBI / "PerformanceAnalytics.pbip").read_text(encoding="utf-8"))
    assert pbip["artifacts"][0]["report"]["path"] == "PerformanceAnalytics.Report"

    pbir = json.loads((POWERBI / "PerformanceAnalytics.Report" / "definition.pbir").read_text(encoding="utf-8"))
    assert pbir["datasetReference"]["byPath"]["path"] == "../PerformanceAnalytics.SemanticModel"
    assert (POWERBI / "PerformanceAnalytics.SemanticModel" / "definition.pbism").exists()


def test_all_model_table_references_resolve() -> None:
    model = (MODEL / "model.tmdl").read_text(encoding="utf-8")
    references = set(re.findall(r"^ref table (.+)$", model, flags=re.MULTILINE))
    files = {path.stem for path in (MODEL / "tables").glob("*.tmdl")}
    assert references == files
    assert "Measures" not in references
    assert "KPI_Measures" in references
    measure_table = (MODEL / "tables" / "KPI_Measures.tmdl").read_text(encoding="utf-8")
    assert "column measure_table_key" in measure_table
    assert "type table [measure_table_key = Int64.Type]" in measure_table
    assert "column _" not in measure_table


def test_relationships_reference_existing_columns() -> None:
    columns: dict[str, set[str]] = {}
    for path in (MODEL / "tables").glob("*.tmdl"):
        text = path.read_text(encoding="utf-8")
        table = re.search(r"^table (.+)$", text, flags=re.MULTILINE)
        assert table
        columns[table.group(1)] = set(re.findall(r"^\tcolumn ([^\r\n]+)$", text, flags=re.MULTILINE))

    relationships = (MODEL / "relationships.tmdl").read_text(encoding="utf-8")
    for table, column in re.findall(r"(?:fromColumn|toColumn): ([^.]+)\.([^\r\n]+)", relationships):
        assert table in columns, f"Unknown relationship table: {table}"
        assert column in columns[table], f"Unknown relationship column: {table}.{column}"


def test_relationship_filter_graph_has_no_ambiguous_paths() -> None:
    relationships = (MODEL / "relationships.tmdl").read_text(encoding="utf-8")
    pairs = re.findall(
        r"fromColumn: ([^.]+)\.[^\r\n]+\s+toColumn: ([^.]+)\.[^\r\n]+",
        relationships,
    )
    graph: dict[str, set[str]] = {}
    for many_table, one_table in pairs:
        graph.setdefault(one_table, set()).add(many_table)

    for origin in graph:
        path_counts: dict[str, int] = {}

        def walk(node: str, seen: frozenset[str]) -> None:
            for target in graph.get(node, set()):
                assert target not in seen, f"Relationship cycle from {origin} through {target}"
                path_counts[target] = path_counts.get(target, 0) + 1
                walk(target, seen | {target})

        walk(origin, frozenset({origin}))
        ambiguous = {target: count for target, count in path_counts.items() if count > 1}
        assert not ambiguous, f"Ambiguous filter paths from {origin}: {ambiguous}"


def test_report_visuals_only_reference_model_fields() -> None:
    table_columns: dict[str, set[str]] = {}
    measures: set[str] = set()
    for path in (MODEL / "tables").glob("*.tmdl"):
        text = path.read_text(encoding="utf-8")
        table = re.search(r"^table (.+)$", text, flags=re.MULTILINE)
        assert table
        table_columns[table.group(1)] = set(re.findall(r"^\tcolumn ([^\r\n]+)$", text, flags=re.MULTILINE))
        measures.update(re.findall(r"^\tmeasure '([^']+)'", text, flags=re.MULTILINE))

    visual_files = list((REPORT / "pages").glob("*/visuals/*/visual.json"))
    for path in visual_files:
        visual = json.loads(path.read_text(encoding="utf-8"))
        query = visual["visual"]["query"]["queryState"]
        for role in query.values():
            for projection in role["projections"]:
                field = projection["field"]
                if "Measure" in field:
                    assert field["Measure"]["Property"] in measures
                elif "Column" in field:
                    column = field["Column"]
                    table = column["Expression"]["SourceRef"]["Entity"]
                    assert column["Property"] in table_columns[table]


def test_power_query_sources_are_centralized() -> None:
    queries = list((POWERBI / "power_query").glob("*.m"))
    assert len(queries) >= 8
    for path in queries:
        text = path.read_text(encoding="utf-8")
        assert "ReadProjectFile(" in text
        assert "File.Contents(" not in text


def test_dashboard_pages_are_populated() -> None:
    pages = json.loads((REPORT / "pages" / "pages.json").read_text(encoding="utf-8"))
    assert len(pages["pageOrder"]) >= 7

    for page_name in pages["pageOrder"]:
        page = json.loads((REPORT / "pages" / page_name / "page.json").read_text(encoding="utf-8"))
        assert page["displayName"]
        assert len(list((REPORT / "pages" / page_name / "visuals").glob("*/visual.json"))) >= 4


def test_table_visuals_have_valid_structure() -> None:
    visual_files = list((REPORT / "pages").glob("*/visuals/*/visual.json"))
    table_visuals = []
    for path in visual_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("visual", {}).get("visualType") == "tableEx":
            table_visuals.append(data["visual"])

    for visual in table_visuals:
        objects = visual.get("objects", {})
        assert "columnHeaders" not in objects, "columnHeaders without selector causes Power BI PivotTableVisuals crash"
        for proj in visual["query"]["queryState"]["Values"]["projections"]:
            assert proj.get("active") is True
