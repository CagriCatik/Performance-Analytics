from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POWERBI = ROOT / "powerbi"
MODEL_NAME = "SaasPulse"
MEASURE_TABLE = "KPI_Measures"
MODEL_DIR = POWERBI / f"{MODEL_NAME}.SemanticModel"
REPORT_DIR = POWERBI / f"{MODEL_NAME}.Report"
QUERY_DIR = POWERBI / "power_query"


TABLES: dict[str, dict] = {
    "DimDate": {
        "query": "date.m",
        "key": "date",
        "columns": [
            ("date", "dateTime"), ("year", "int64"), ("month_number", "int64"),
            ("month", "string"), ("year_month", "string"), ("month_start", "dateTime"),
            ("is_working_day", "boolean"),
        ],
        "sort": {"month": "month_number", "year_month": "month_start"},
    },
    "DimAccount": {
        "query": "accounts.m", "key": "account_id",
        "columns": [
            ("account_id", "string"), ("account_name", "string"), ("country", "string"),
            ("region", "string"), ("city", "string"), ("latitude", "double"),
            ("longitude", "double"), ("segment", "string"), ("industry", "string"),
        ],
    },
    "DimSubscription": {
        "query": "subscriptions.m", "key": "subscription_id",
        "columns": [
            ("subscription_id", "string"), ("account_id", "string"), ("plan_name", "string"),
            ("plan_tier", "string"), ("billing_cycle", "string"), ("annual_value_eur", "double"),
            ("mrr_eur", "double"), ("start_date", "dateTime"), ("end_date", "string"),
            ("status", "string"), ("age_months", "int64"), ("max_users", "int64"),
            ("country", "string"), ("region", "string"),
        ],
    },
    "DimPlan": {
        "query": "plans_catalog.m", "key": "plan_name",
        "columns": [
            ("plan_name", "string"), ("tier", "string"), ("monthly_price_eur", "double"),
            ("annual_price_eur", "double"), ("max_users", "int64"), ("churn_base", "double"),
        ],
    },
    "DimRegion": {
        "query": "regions.m", "key": "region", "columns": [("region", "string")],
    },
    "DimSegmentBand": {
        "m": 'let Source = #table(type table [band = text, sort_order = Int64.Type], {{"SMB", 1}, {"Mid-Market", 2}, {"Enterprise", 3}}) in Source',
        "key": "band",
        "columns": [("band", "string"), ("sort_order", "int64")],
        "sort": {"band": "sort_order"},
    },
    "FactMonthlyMetrics": {
        "query": "monthly_metrics.m",
        "columns": [
            ("month_date", "dateTime"), ("subscription_id", "string"), ("account_id", "string"),
            ("plan_name", "string"), ("mrr_eur", "double"), ("active_users", "int64"),
            ("licensed_users", "int64"), ("active_user_ratio", "double"), ("api_calls", "int64"),
            ("storage_gb", "double"), ("feature_adoption_pct", "double"),
            ("nps_score", "int64"), ("revenue_at_risk_eur", "double"),
        ],
    },
    "FactSubscriptionEvents": {
        "query": "subscription_events.m",
        "columns": [
            ("event_id", "string"), ("subscription_id", "string"), ("account_id", "string"),
            ("event_type", "string"), ("event_date", "dateTime"), ("event_timestamp", "dateTime"),
            ("from_plan", "string"), ("to_plan", "string"), ("mrr_change_eur", "double"),
            ("region", "string"), ("country", "string"),
        ],
    },
    "FactSupportTickets": {
        "query": "support_tickets.m",
        "columns": [
            ("ticket_id", "string"), ("subscription_id", "string"), ("account_id", "string"),
            ("opened_at", "dateTime"), ("closed_at", "string"), ("category", "string"),
            ("severity", "string"), ("status", "string"), ("resolution_hours", "double"),
            ("first_contact_resolution", "boolean"), ("escalated", "boolean"),
            ("opened_date", "dateTime"), ("country", "string"), ("region", "string"),
            ("plan_name", "string"),
        ],
    },
    "FactRefunds": {
        "query": "refunds.m",
        "columns": [
            ("refund_id", "string"), ("ticket_id", "string"), ("subscription_id", "string"),
            ("account_id", "string"), ("claim_date", "dateTime"), ("reason", "string"),
            ("amount_eur", "double"), ("approved", "boolean"), ("plan_name", "string"),
            ("country", "string"), ("region", "string"),
        ],
    },
    "FactLiveActivity": {
        "query": "live_activity.m",
        "key": "subscription_id",
        "columns": [
            ("subscription_id", "string"), ("account_id", "string"), ("plan_name", "string"),
            ("status", "string"), ("active_users", "int64"), ("max_users", "int64"),
            ("current_feature", "string"), ("session_duration_min", "double"),
            ("api_requests_last_hour", "int64"), ("last_updated", "dateTime"),
        ],
    },
}


MEASURES = [
    # Accounts & Subscriptions
    ("Accounts", "DISTINCTCOUNT(DimAccount[account_id])", "#,0"),
    ("Active Subscriptions", 'CALCULATE(DISTINCTCOUNT(DimSubscription[subscription_id]), DimSubscription[status] = "Active")', "#,0"),
    ("Total Subscriptions", "DISTINCTCOUNT(DimSubscription[subscription_id])", "#,0"),
    ("Churned Subscriptions", 'CALCULATE(DISTINCTCOUNT(DimSubscription[subscription_id]), DimSubscription[status] = "Churned")', "#,0"),
    ("Trial Subscriptions", 'CALCULATE(DISTINCTCOUNT(DimSubscription[subscription_id]), DimSubscription[status] = "Trial")', "#,0"),
    ("Suspended Subscriptions", 'CALCULATE(DISTINCTCOUNT(DimSubscription[subscription_id]), DimSubscription[status] = "Suspended")', "#,0"),

    # Revenue
    ("Total ARR EUR", "SUMX(FILTER(DimSubscription, DimSubscription[status] = \"Active\"), DimSubscription[annual_value_eur])", "€#,0;(-€#,0);€0"),
    ("Total MRR EUR", "SUMX(FILTER(DimSubscription, DimSubscription[status] = \"Active\"), DimSubscription[mrr_eur])", "€#,0;(-€#,0);€0"),
    ("Average MRR per Subscription EUR", "DIVIDE([Total MRR EUR], [Active Subscriptions])", "€#,0.00;(-€#,0.00);€0"),
    ("Monthly Revenue EUR", "SUM(FactMonthlyMetrics[mrr_eur])", "€#,0;(-€#,0);€0"),
    ("Revenue at Risk EUR", "SUM(FactMonthlyMetrics[revenue_at_risk_eur])", "€#,0;(-€#,0);€0"),
    ("Revenue at Risk %", "DIVIDE([Revenue at Risk EUR], [Monthly Revenue EUR])", "0.0%"),

    # Churn
    ("Churn Rate %", "DIVIDE([Churned Subscriptions], [Total Subscriptions])", "0.0%"),
    ("Logo Churn Rate %", '''VAR TotalAccounts = DISTINCTCOUNT(DimAccount[account_id])
VAR ChurnedAccounts = CALCULATE(DISTINCTCOUNT(DimSubscription[account_id]), DimSubscription[status] = "Churned")
RETURN DIVIDE(ChurnedAccounts, TotalAccounts)''', "0.0%"),
    ("Total Subscription Events", "COUNTROWS(FactSubscriptionEvents)", "#,0"),
    ("Churn Events", 'CALCULATE(COUNTROWS(FactSubscriptionEvents), FactSubscriptionEvents[event_type] = "Churn")', "#,0"),
    ("Upgrade Events", 'CALCULATE(COUNTROWS(FactSubscriptionEvents), FactSubscriptionEvents[event_type] = "Upgrade")', "#,0"),
    ("Downgrade Events", 'CALCULATE(COUNTROWS(FactSubscriptionEvents), FactSubscriptionEvents[event_type] = "Downgrade")', "#,0"),
    ("Renewal Events", 'CALCULATE(COUNTROWS(FactSubscriptionEvents), FactSubscriptionEvents[event_type] = "Renewal")', "#,0"),
    ("Net MRR Movement EUR", "SUM(FactSubscriptionEvents[mrr_change_eur])", "€#,0;(-€#,0);€0"),
    ("Expansion MRR EUR", "CALCULATE(SUM(FactSubscriptionEvents[mrr_change_eur]), FactSubscriptionEvents[event_type] = \"Upgrade\")", "€#,0;(-€#,0);€0"),
    ("Contraction MRR EUR", "CALCULATE(SUM(FactSubscriptionEvents[mrr_change_eur]), FactSubscriptionEvents[event_type] IN {\"Downgrade\", \"Churn\"})", "€#,0;(-€#,0);€0"),

    # Engagement
    ("Average Active User Ratio", "AVERAGE(FactMonthlyMetrics[active_user_ratio])", "0.0%"),
    ("Total Active Users", "SUM(FactMonthlyMetrics[active_users])", "#,0"),
    ("Total Licensed Users", "SUM(FactMonthlyMetrics[licensed_users])", "#,0"),
    ("Average NPS Score", "AVERAGE(FactMonthlyMetrics[nps_score])", "0.0"),
    ("Average Feature Adoption %", "AVERAGE(FactMonthlyMetrics[feature_adoption_pct])", "0.0%"),
    ("Total API Calls", "SUM(FactMonthlyMetrics[api_calls])", "#,0"),
    ("Average Storage GB", "AVERAGE(FactMonthlyMetrics[storage_gb])", "0.00"),

    # Support
    ("Support Tickets", "DISTINCTCOUNT(FactSupportTickets[ticket_id])", "#,0"),
    ("Open Tickets", 'CALCULATE([Support Tickets], FactSupportTickets[status] = "Open")', "#,0"),
    ("Closed Tickets", 'CALCULATE([Support Tickets], FactSupportTickets[status] = "Closed")', "#,0"),
    ("Critical Tickets", 'CALCULATE([Support Tickets], FactSupportTickets[severity] = "Critical")', "#,0"),
    ("Open Critical Tickets", 'CALCULATE([Support Tickets], FactSupportTickets[status] = "Open", FactSupportTickets[severity] = "Critical")', "#,0"),
    ("Ticket Closure Rate %", "DIVIDE([Closed Tickets], [Support Tickets])", "0.0%"),
    ("First Contact Resolution %", 'DIVIDE(CALCULATE([Support Tickets], FactSupportTickets[first_contact_resolution] = TRUE()), CALCULATE([Support Tickets], FactSupportTickets[status] = "Closed"))', "0.0%"),
    ("Escalation Rate %", "DIVIDE(CALCULATE([Support Tickets], FactSupportTickets[escalated] = TRUE()), [Support Tickets])", "0.0%"),
    ("Average Resolution Hours", "AVERAGE(FactSupportTickets[resolution_hours])", "0.0"),
    ("Tickets per Subscription", "DIVIDE([Support Tickets], [Active Subscriptions])", "0.00"),

    # Refunds
    ("Refund Requests", "DISTINCTCOUNT(FactRefunds[refund_id])", "#,0"),
    ("Approved Refunds", "CALCULATE([Refund Requests], FactRefunds[approved] = TRUE())", "#,0"),
    ("Refund Approval %", "DIVIDE([Approved Refunds], [Refund Requests])", "0.0%"),
    ("Refund Amount EUR", "CALCULATE(SUM(FactRefunds[amount_eur]), FactRefunds[approved] = TRUE())", "€#,0;(-€#,0);€0"),
    ("Average Refund EUR", "DIVIDE([Refund Amount EUR], [Approved Refunds])", "€#,0.00"),
    ("Refund Rate %", "DIVIDE([Refund Requests], [Support Tickets])", "0.0%"),

    # Risk scoring
    ("Subscription Health Score", '''VAR ChurnRisk = [Churn Rate %]
VAR LowAdoption = CALCULATE([Average Feature Adoption %]) < 0.40
VAR HighRisk = CALCULATE([Revenue at Risk %]) > 0.20
VAR TicketsHigh = CALCULATE([Tickets per Subscription]) > 3
RETURN MAX(0, 100 - IF(ChurnRisk > 0.1, 30, 0) - IF(LowAdoption, 20, 0) - IF(HighRisk, 25, 0) - IF(TicketsHigh, 15, 0))''', "0"),

    ("Health Score Color", '''VAR Score = [Subscription Health Score]
RETURN SWITCH(TRUE(), Score >= 80, "#1AAB40", Score >= 60, "#118DFF", Score >= 40, "#E66C37", "#D64550")''', "@"),

    # Live activity
    ("Live Active Sessions", 'CALCULATE(COUNTROWS(FactLiveActivity), FactLiveActivity[status] = "Active Session")', "#,0"),
    ("Live Idle Sessions", 'CALCULATE(COUNTROWS(FactLiveActivity), FactLiveActivity[status] = "Idle")', "#,0"),
    ("Live Connected Subscriptions", "COUNTROWS(FactLiveActivity)", "#,0"),
    ("Live Total Active Users", "SUM(FactLiveActivity[active_users])", "#,0"),
    ("Live Avg Session Duration Min", "AVERAGE(FactLiveActivity[session_duration_min])", "0.0"),
    ("Live API Requests/Hour", "SUM(FactLiveActivity[api_requests_last_hour])", "#,0"),

    # Period-over-period
    ("MRR Previous Month EUR", "CALCULATE([Monthly Revenue EUR], DATEADD(DimDate[date], -1, MONTH))", "€#,0;(-€#,0);€0"),
    ("MRR MoM Growth %", "DIVIDE([Monthly Revenue EUR] - [MRR Previous Month EUR], [MRR Previous Month EUR])", "0.0%"),
    ("Tickets Previous Month", "CALCULATE([Support Tickets], DATEADD(DimDate[date], -1, MONTH))", "#,0"),
    ("Tickets MoM %", "DIVIDE([Support Tickets] - [Tickets Previous Month], [Tickets Previous Month])", "0.0%"),
    ("Data Snapshot Date", 'FORMAT(MAX(FactMonthlyMetrics[month_date]), "yyyy-MM-dd")', "@"),

    # Targets
    ("MRR Growth Target %", "0.05", "0.0%"),
    ("FCR Target %", "0.75", "0.0%"),
    ("Feature Adoption Target %", "0.60", "0.0%"),
    ("NPS Target", "40", "0"),
]


RELATIONSHIPS = [
    ("metrics-date", "FactMonthlyMetrics.month_date", "DimDate.date"),
    ("metrics-subscription", "FactMonthlyMetrics.subscription_id", "DimSubscription.subscription_id"),
    ("events-date", "FactSubscriptionEvents.event_date", "DimDate.date"),
    ("events-subscription", "FactSubscriptionEvents.subscription_id", "DimSubscription.subscription_id"),
    ("tickets-date", "FactSupportTickets.opened_date", "DimDate.date"),
    ("tickets-subscription", "FactSupportTickets.subscription_id", "DimSubscription.subscription_id"),
    ("refunds-date", "FactRefunds.claim_date", "DimDate.date"),
    ("refunds-subscription", "FactRefunds.subscription_id", "DimSubscription.subscription_id"),
    ("subscription-account", "DimSubscription.account_id", "DimAccount.account_id"),
    ("subscription-plan", "DimSubscription.plan_name", "DimPlan.plan_name"),
    ("subscription-region", "DimSubscription.region", "DimRegion.region"),
    ("live-subscription", "FactLiveActivity.subscription_id", "DimSubscription.subscription_id"),
]


def _write(path: Path, value: str | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, dict):
        value = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    path.write_text(value, encoding="utf-8", newline="\n")


def _indent_expression(expression: str, levels: int = 3) -> str:
    prefix = "\t" * levels
    return "\n".join(prefix + line if line else "" for line in expression.splitlines())


def _column_block(name: str, data_type: str, *, key: bool = False, sort_by: str | None = None) -> str:
    lines = [f"\tcolumn {name}", f"\t\tdataType: {data_type}"]
    if key:
        lines.append("\t\tisKey")
    if sort_by:
        lines.append(f"\t\tsortByColumn: {sort_by}")
    if name in {"latitude"}:
        lines.append("\t\tdataCategory: Latitude")
    elif name in {"longitude"}:
        lines.append("\t\tdataCategory: Longitude")
    elif name in {"country"}:
        lines.append("\t\tdataCategory: Country")
    elif name in {"city"}:
        lines.append("\t\tdataCategory: City")
    lines.extend(["\t\tsummarizeBy: none", f"\t\tsourceColumn: {name}"])
    return "\n".join(lines)


def _table_tmdl(name: str, config: dict) -> str:
    m_expression = config.get("m") or (QUERY_DIR / config["query"]).read_text(encoding="utf-8").strip()
    blocks = [f"table {name}"]
    for column_name, data_type in config["columns"]:
        blocks.append(_column_block(
            column_name, data_type,
            key=column_name == config.get("key"),
            sort_by=config.get("sort", {}).get(column_name),
        ))
    blocks.append(
        f"\tpartition {name} = m\n"
        "\t\tmode: import\n"
        "\t\tsource =\n"
        f"{_indent_expression(m_expression)}"
    )
    return "\n\n".join(blocks) + "\n"


def _measures_tmdl() -> str:
    blocks = [f"table {MEASURE_TABLE}", "\tcolumn measure_table_key", "\t\tdataType: int64", "\t\tsourceColumn: measure_table_key", "\t\tisHidden", "\t\tsummarizeBy: none"]
    for name, expression, format_string in MEASURES:
        if "\n" in expression:
            measure = f"\tmeasure '{name}' = ```\n{_indent_expression(expression, 3)}\n\t\t```\n\t\tformatString: {format_string}"
        else:
            measure = f"\tmeasure '{name}' = {expression}\n\t\tformatString: {format_string}"
        blocks.append(measure)
    blocks.append(
        f"\tpartition {MEASURE_TABLE} = m\n"
        "\t\tmode: import\n"
        "\t\tsource =\n"
        "\t\t\tlet\n"
        "\t\t\t\tSource = #table(type table [measure_table_key = Int64.Type], {{1}})\n"
        "\t\t\tin\n"
        "\t\t\t\tSource"
    )
    return "\n\n".join(blocks) + "\n"


def _expressions_tmdl(source_kind: str, source_root: str) -> str:
    safe_root = source_root.replace('"', '""')
    if source_kind == "local":
        reader = '(relativePath as text) as binary => File.Contents(ProjectDataRoot & "\\" & Text.Replace(relativePath, "/", "\\"))'
    else:
        reader = '(relativePath as text) as binary => AzureStorage.BlobContents(ProjectDataRoot & "/" & relativePath)'
    return (
        f'expression ProjectDataRoot = "{safe_root}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n\n'
        f"expression ReadProjectFile = {reader}\n\n"
        'expression NormalizeCountry = (value as nullable text) as nullable text => let key = if value = null then null else Text.Upper(Text.Trim(value)), mapping = [DE="Germany", GERMANY="Germany", DEUTSCHLAND="Germany", FR="France", FRANCE="France", ES="Spain", SPAIN="Spain", IT="Italy", ITALY="Italy", AT="Austria", AUSTRIA="Austria", CH="Switzerland", SWITZERLAND="Switzerland", BE="Belgium", BELGIUM="Belgium", NL="Netherlands", NETHERLANDS="Netherlands"] in if key = null then null else Record.FieldOrDefault(mapping, key, Text.Proper(Text.Trim(value)))\n\n'
        'expression DataSnapshotDate = let manifest = Json.Document(ReadProjectFile("raw/manifest.json")), snapshot = Date.FromText(manifest[time_range][end]) in snapshot\n'
    )


def _measure_projection(name: str) -> dict:
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": MEASURE_TABLE}}, "Property": name}},
        "queryRef": f"{MEASURE_TABLE}.{name}", "nativeQueryRef": name, "active": True,
    }


def _column_projection(table: str, column: str) -> dict:
    return {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}},
        "queryRef": f"{table}.{column}", "nativeQueryRef": column, "active": True,
    }


def _title(text: str) -> dict:
    return {"title": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "text": {"expr": {"Literal": {"Value": f"'{text}'"}}}}}]}


VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"

CANVAS_WIDTH, CANVAS_HEIGHT, MARGIN, GAP = 1920, 1080, 40, 20
SLICER_Y, SLICER_HEIGHT = 20, 64
CARD_Y, CARD_HEIGHT = 100, 140
ROW1_Y, ROW1_HEIGHT = 265, 360
ROW2_Y, ROW2_HEIGHT = 650, 390


def _container(name: str, visual: dict, x: int, y: int, width: int, height: int, order: int) -> dict:
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": order, "width": width, "height": height, "tabOrder": order},
        "visual": visual,
    }


def _stack(visuals: list[dict]) -> list[dict]:
    for order, visual in enumerate(visuals):
        visual["position"]["z"] = order
        visual["position"]["tabOrder"] = order
    return visuals


def _card(name: str, measures: list[str], x: int, y: int, width: int, height: int, order: int) -> dict:
    visual = {"visualType": "cardVisual", "query": {"queryState": {"Data": {"projections": [_measure_projection(m) for m in measures]}}}, "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _chart(name: str, visual_type: str, title: str, category: tuple[str, str], measures: list[str], x: int, y: int, width: int, height: int, order: int, *, series: tuple[str, str] | None = None, y2: list[str] | None = None) -> dict:
    if visual_type == "treemap":
        query_state = {
            "Group": {"projections": [_column_projection(*category)]},
            "Values": {"projections": [_measure_projection(m) for m in measures]},
        }
        if series:
            query_state["Details"] = {"projections": [_column_projection(*series)]}
    else:
        query_state = {"Category": {"projections": [_column_projection(*category)]}}
        if series:
            query_state["Series"] = {"projections": [_column_projection(*series)]}
        query_state["Y"] = {"projections": [_measure_projection(m) for m in measures]}
        if y2:
            query_state["Y2"] = {"projections": [_measure_projection(m) for m in y2]}
    visual = {"visualType": visual_type, "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _table_visual(name: str, title: str, fields: list[tuple[str, str, str]], x: int, y: int, width: int, height: int, order: int, *, sort: tuple[str, str] | None = None, color_by: dict[str, str] | None = None) -> dict:
    projections = []
    for kind, table, field_name in fields:
        projection = _measure_projection(field_name) if kind == "measure" else _column_projection(table, field_name)
        projections.append(projection)
    query: dict = {"queryState": {"Values": {"projections": projections}}}
    if sort:
        sort_measure, direction = sort
        query["sortDefinition"] = {
            "sort": [{"field": {"Measure": {"Expression": {"SourceRef": {"Entity": MEASURE_TABLE}}, "Property": sort_measure}}, "direction": direction}],
            "isDefaultSort": False,
        }
    visual: dict = {"visualType": "tableEx", "query": query, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    if color_by:
        visual["objects"] = {"values": [_font_color_from_measure(shown, color) for shown, color in color_by.items()]}
    return _container(name, visual, x, y, width, height, order)


def _font_color_from_measure(displayed_measure: str, color_measure: str) -> dict:
    return {
        "properties": {"fontColor": {"solid": {"color": {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": MEASURE_TABLE}}, "Property": color_measure}}}}}},
        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"{MEASURE_TABLE}.{displayed_measure}"},
    }


def _slicer(name: str, title: str, field: tuple[str, str], x: int, y: int, width: int, height: int, order: int, sync_group: str, *, mode: str = "Dropdown") -> dict:
    objects = {}
    if mode == "Dropdown":
        objects = {"data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}]}
    visual = {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [_column_projection(*field)]}}},
        "objects": objects,
        "visualContainerObjects": _title(title),
        "drillFilterOtherVisuals": True,
        "syncGroup": {"groupName": sync_group, "fieldChanges": True, "filterChanges": True},
    }
    return _container(name, visual, x, y, width, height, order)


def _slicer_row(prefix: str, fields: list[tuple[str, str, str]]) -> list[dict]:
    width = (CANVAS_WIDTH - 2 * MARGIN - GAP * (len(fields) - 1)) // len(fields)
    return [
        _slicer(f"{prefix}_slicer_{column}", title, (table, column), MARGIN + index * (width + GAP), SLICER_Y, width, SLICER_HEIGHT, 0, f"sync_{table}_{column}".lower())
        for index, (title, table, column) in enumerate(fields)
    ]


def _kpi_row(name: str, measures: list[str]) -> dict:
    return _card(name, measures, MARGIN, CARD_Y, CANVAS_WIDTH - 2 * MARGIN, CARD_HEIGHT, 0)


def _scatter(name: str, title: str, category: tuple[str, str], x_measure: str, y_measure: str, size_measure: str, x: int, y: int, width: int, height: int, order: int) -> dict:
    query_state = {
        "Category": {"projections": [_column_projection(*category)]},
        "X": {"projections": [_measure_projection(x_measure)]},
        "Y": {"projections": [_measure_projection(y_measure)]},
        "Size": {"projections": [_measure_projection(size_measure)]},
    }
    visual = {"visualType": "scatterChart", "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _gauge(name: str, title: str, measure: str, target: str | None, x: int, y: int, width: int, height: int, order: int) -> dict:
    query_state = {"Y": {"projections": [_measure_projection(measure)]}}
    if target:
        query_state["TargetValue"] = {"projections": [_measure_projection(target)]}
    visual = {"visualType": "gauge", "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _multi_row_card(name: str, title: str, measures: list[str], x: int, y: int, width: int, height: int, order: int) -> dict:
    query_state = {"Values": {"projections": [_measure_projection(m) for m in measures]}}
    visual = {"visualType": "multiRowCard", "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _kpi_visual(name: str, title: str, indicator: str, trend: tuple[str, str], target: str | None, x: int, y: int, width: int, height: int, order: int) -> dict:
    query_state = {
        "Indicator": {"projections": [_measure_projection(indicator)]},
        "TrendAxis": {"projections": [_column_projection(*trend)]},
    }
    if target:
        query_state["Goal"] = {"projections": [_measure_projection(target)]}
    visual = {"visualType": "kpi", "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _matrix(name: str, title: str, rows: list[tuple[str, str]], measures: list[str], x: int, y: int, width: int, height: int, order: int, *, columns: list[tuple[str, str]] | None = None) -> dict:
    query_state = {
        "Rows": {"projections": [_column_projection(*row) for row in rows]},
        "Values": {"projections": [_measure_projection(m) for m in measures]},
    }
    if columns:
        query_state["Columns"] = {"projections": [_column_projection(*col) for col in columns]}
    visual = {"visualType": "pivotTable", "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _churn_by_segment(name: str, title: str, measure: str, explain_by: list[tuple[str, str]], x: int, y: int, width: int, height: int, order: int) -> dict:
    query_state = {
        "Category": {"projections": [_column_projection(*explain_by[0])]},
        "Series": {"projections": [_column_projection(*explain_by[1])] if len(explain_by) > 1 else []},
        "Y": {"projections": [_measure_projection(measure)]},
    }
    if not query_state["Series"]["projections"]:
        del query_state["Series"]
    visual = {"visualType": "clusteredBarChart", "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _churn_rate_by_plan(name: str, title: str, measure: str, explain_by: list[tuple[str, str]], x: int, y: int, width: int, height: int, order: int) -> dict:
    query_state = {
        "Category": {"projections": [_column_projection(*explain_by[0])]},
        "Y": {"projections": [_measure_projection(measure)]},
    }
    visual = {"visualType": "clusteredColumnChart", "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _smart_narrative(name: str, title: str, measures: list[str], x: int, y: int, width: int, height: int, order: int) -> dict:
    query_state = {"Values": {"projections": [_measure_projection(m) for m in measures]}}
    visual = {"visualType": "multiRowCard", "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _anomaly_chart(name: str, title: str, category: tuple[str, str], measure: str, x: int, y: int, width: int, height: int, order: int) -> dict:
    query_state = {
        "Category": {"projections": [_column_projection(*category)]},
        "Y": {"projections": [_measure_projection(measure)]},
    }
    objects = {"anomalyDetection": [{"properties": {"enabled": {"expr": {"Literal": {"Value": "true"}}}}}]}
    visual = {"visualType": "lineChart", "query": {"queryState": query_state}, "objects": objects, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _filled_map(name: str, title: str, location: tuple[str, str], measure: str, x: int, y: int, width: int, height: int, order: int) -> dict:
    query_state = {
        "Location": {"projections": [_column_projection(*location)]},
        "Size": {"projections": [_measure_projection(measure)]},
    }
    visual = {"visualType": "filledMap", "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _bubble_map(name: str, title: str, latitude: tuple[str, str], longitude: tuple[str, str], size_measure: str, series: tuple[str, str] | None, x: int, y: int, width: int, height: int, order: int) -> dict:
    query_state = {
        "Latitude": {"projections": [_column_projection(*latitude)]},
        "Longitude": {"projections": [_column_projection(*longitude)]},
        "Size": {"projections": [_measure_projection(size_measure)]},
    }
    if series:
        query_state["Series"] = {"projections": [_column_projection(*series)]}
    visual = {"visualType": "map", "query": {"queryState": query_state}, "visualContainerObjects": _title(title), "drillFilterOtherVisuals": True}
    return _container(name, visual, x, y, width, height, order)


def _live_table(name: str, title: str, fields: list[tuple[str, str, str]], x: int, y: int, width: int, height: int, order: int) -> dict:
    return _table_visual(name, title, fields, x, y, width, height, order)


PAGES = [
    ("executive_overview", "Executive Overview", [
        _card("exec_kpis", ["Active Subscriptions", "Total ARR EUR", "Churn Rate %", "First Contact Resolution %", "Average NPS Score", "Revenue at Risk EUR"], 40, 25, 1340, 130, 0),
        _gauge("mrr_growth_gauge", "MRR Growth vs. Target", "MRR MoM Growth %", "MRR Growth Target %", 1400, 25, 480, 130, 1),
        _chart("mrr_trend", "lineClusteredColumnComboChart", "Monthly Revenue & Net MRR Movement", ("DimDate", "year_month"), ["Monthly Revenue EUR"], 40, 185, 920, 370, 2, y2=["Net MRR Movement EUR"]),
        _chart("plan_donut", "donutChart", "Subscriptions by Plan", ("DimSubscription", "plan_name"), ["Active Subscriptions"], 980, 185, 900, 370, 3),
        _chart("churn_trend", "areaChart", "Churn Events Over Time", ("DimDate", "year_month"), ["Churn Events", "Upgrade Events"], 40, 585, 920, 455, 4),
        _chart("segment_treemap", "treemap", "ARR Distribution by Account Segment", ("DimAccount", "segment"), ["Total ARR EUR"], 980, 585, 900, 455, 5),
    ]),
    ("revenue_analytics", "Revenue Analytics", [
        _card("rev_kpis", ["Total MRR EUR", "Total ARR EUR", "Average MRR per Subscription EUR", "Expansion MRR EUR", "Contraction MRR EUR", "Revenue at Risk EUR"], 40, 25, 1840, 130, 0),
        _chart("mrr_waterfall", "waterfallChart", "Monthly MRR Waterfall: Expansion vs. Contraction", ("DimDate", "year_month"), ["Net MRR Movement EUR"], 40, 185, 920, 380, 1),
        _chart("plan_revenue_col", "clusteredColumnChart", "MRR Contribution by Plan Tier", ("DimSubscription", "plan_tier"), ["Monthly Revenue EUR"], 980, 185, 900, 380, 2),
        _chart("revenue_region_100", "hundredPercentStackedColumnChart", "Revenue Mix by Region", ("DimRegion", "region"), ["Monthly Revenue EUR"], 40, 595, 920, 445, 3, series=("DimSubscription", "plan_name")),
        _chart("rev_segment_bar", "barChart", "Revenue at Risk by Segment", ("DimAccount", "segment"), ["Revenue at Risk EUR"], 980, 595, 900, 445, 4),
    ]),
    ("churn_retention", "Churn & Retention", [
        _card("churn_kpis", ["Churned Subscriptions", "Churn Rate %", "Logo Churn Rate %", "Churn Events", "Downgrade Events", "Renewal Events"], 40, 25, 1840, 130, 0),
        _chart("churn_kpi_trend", "lineChart", "Monthly Churn Rate Trend", ("DimDate", "year_month"), ["Churn Rate %"], 40, 185, 600, 350, 1),
        _chart("events_combo", "lineStackedColumnComboChart", "Subscription Events Over Time", ("DimDate", "year_month"), ["Churn Events", "Upgrade Events"], 660, 185, 1260, 350, 2, y2=["Downgrade Events"]),
        _chart("event_type_funnel", "funnel", "Event Type Distribution", ("FactSubscriptionEvents", "event_type"), ["Total Subscription Events"], 40, 565, 550, 465, 3),
        _chart("retention_plan_ribbon", "ribbonChart", "Subscription Retention by Plan over Time", ("DimDate", "year_month"), ["Active Subscriptions"], 610, 565, 1290, 465, 4, series=("DimSubscription", "plan_name")),
    ]),
    ("account_portfolio", "Account Portfolio", [
        _card("account_kpis", ["Accounts", "Active Subscriptions", "Total ARR EUR", "Average MRR per Subscription EUR", "Churn Rate %", "Average NPS Score"], 40, 25, 1840, 130, 0),
        _chart("account_segment_donut", "donutChart", "Accounts by Segment", ("DimAccount", "segment"), ["Accounts"], 40, 185, 540, 360, 1),
        _chart("account_industry_treemap", "treemap", "ARR by Industry Vertical", ("DimAccount", "industry"), ["Total ARR EUR"], 600, 185, 920, 360, 2),
        _scatter("account_scatter", "Account Size vs. Revenue Risk", ("DimAccount", "account_name"), "Active Subscriptions", "Revenue at Risk EUR", "Total ARR EUR", 1540, 185, 340, 360, 3),
        _table_visual("account_detail", "Account portfolio detail", [
            ("column", "DimAccount", "account_name"), ("column", "DimAccount", "country"),
            ("column", "DimAccount", "segment"), ("column", "DimAccount", "industry"),
            ("measure", "", "Active Subscriptions"), ("measure", "", "Total ARR EUR"),
            ("measure", "", "Average NPS Score"), ("measure", "", "Churn Rate %"),
        ], 40, 565, 1840, 465, 4),
    ]),
    ("engagement_product", "Product Engagement", [
        _card("engage_kpis", ["Average Active User Ratio", "Average Feature Adoption %", "Average NPS Score", "Total API Calls", "Average Storage GB"], 40, 25, 1340, 130, 0),
        _gauge("adoption_gauge", "Feature Adoption vs. Target", "Average Feature Adoption %", "Feature Adoption Target %", 1400, 25, 480, 130, 1),
        _chart("nps_trend", "lineChart", "NPS Score Trend", ("DimDate", "year_month"), ["Average NPS Score"], 40, 185, 920, 370, 2),
        _chart("feature_plan_bar", "clusteredBarChart", "Feature Adoption by Plan", ("DimSubscription", "plan_name"), ["Average Feature Adoption %"], 980, 185, 900, 370, 3),
        _chart("api_calls_area", "stackedAreaChart", "API Calls Trend by Tier", ("DimDate", "year_month"), ["Total API Calls"], 40, 585, 920, 455, 4, series=("DimSubscription", "plan_tier")),
        _chart("user_ratio_col", "columnChart", "Active User Ratio by Segment", ("DimAccount", "segment"), ["Average Active User Ratio"], 980, 585, 900, 455, 5),
    ]),
    ("support_operations", "Support Operations", [
        _card("support_kpis", ["Support Tickets", "Open Tickets", "Critical Tickets", "First Contact Resolution %", "Escalation Rate %", "Average Resolution Hours"], 40, 25, 1840, 130, 0),
        _chart("ticket_trend", "lineClusteredColumnComboChart", "Ticket Volume & Resolution Trend", ("DimDate", "year_month"), ["Support Tickets", "Open Tickets"], 40, 185, 920, 370, 1, y2=["Average Resolution Hours"]),
        _chart("ticket_category_donut", "donutChart", "Tickets by Category", ("FactSupportTickets", "category"), ["Support Tickets"], 980, 185, 900, 370, 2),
        _chart("ticket_severity_funnel", "funnel", "Ticket Severity Pipeline", ("FactSupportTickets", "severity"), ["Support Tickets"], 40, 585, 550, 455, 3),
        _matrix("ticket_region_matrix", "Regional Severity Matrix", [("DimRegion", "region")], ["Support Tickets", "Average Resolution Hours"], 610, 585, 1270, 455, 4, columns=[("FactSupportTickets", "severity")]),
    ]),
    ("refunds_analysis", "Refunds & Financial Ops", [
        _card("refund_kpis", ["Refund Requests", "Approved Refunds", "Refund Approval %", "Refund Amount EUR", "Average Refund EUR", "Refund Rate %"], 40, 25, 1840, 130, 0),
        _chart("refund_reason_col", "clusteredColumnChart", "Refund Requests by Reason", ("FactRefunds", "reason"), ["Refund Requests", "Refund Amount EUR"], 40, 185, 920, 380, 1),
        _chart("refund_plan_donut", "donutChart", "Refund Amount by Plan", ("FactRefunds", "plan_name"), ["Refund Amount EUR"], 980, 185, 900, 380, 2),
        _chart("refund_trend", "areaChart", "Monthly Refund Amount Trend", ("DimDate", "year_month"), ["Refund Amount EUR"], 40, 595, 920, 455, 3),
        _chart("refund_country_bar", "barChart", "Approved Refunds by Country", ("FactRefunds", "country"), ["Approved Refunds"], 980, 595, 900, 455, 4),
    ]),
    ("geographic_analysis", "Geographic Analysis", [
        _card("geo_kpis", ["Accounts", "Active Subscriptions", "Total ARR EUR", "Support Tickets"], 40, 25, 1840, 130, 0),
        _filled_map("account_filled_map", "Active Subscriptions by Country", ("DimAccount", "country"), "Active Subscriptions", 40, 185, 950, 480, 1),
        _chart("region_arpu_col", "clusteredColumnChart", "ARR & Churn by Region", ("DimRegion", "region"), ["Total ARR EUR", "Churned Subscriptions"], 1010, 185, 870, 480, 2),
        _chart("country_plan_100", "hundredPercentStackedColumnChart", "Plan Mix by Country", ("DimAccount", "country"), ["Active Subscriptions"], 40, 690, 950, 360, 3, series=("DimSubscription", "plan_name")),
        _chart("geo_segment_donut", "donutChart", "Segment Distribution", ("DimAccount", "segment"), ["Accounts"], 1010, 690, 870, 360, 4),
    ]),
    ("plan_performance", "Plan Performance", [
        _card("plan_kpis", ["Active Subscriptions", "Total ARR EUR", "Average MRR per Subscription EUR", "Churn Rate %", "Average Feature Adoption %"], 40, 25, 1840, 130, 0),
        _chart("plan_arr_bar", "barChart", "ARR Contribution by Plan", ("DimSubscription", "plan_name"), ["Total ARR EUR"], 40, 185, 550, 370, 1),
        _chart("plan_tier_100", "hundredPercentStackedColumnChart", "Billing Cycle Mix by Tier", ("DimSubscription", "plan_tier"), ["Active Subscriptions"], 620, 185, 600, 370, 2, series=("DimSubscription", "billing_cycle")),
        _matrix("plan_industry_matrix", "Plan x Industry Revenue Matrix", [("DimSubscription", "plan_name")], ["Active Subscriptions", "Total ARR EUR", "Churn Rate %"], 1240, 185, 640, 370, 3, columns=[("DimAccount", "industry")]),
        _chart("plan_events_line", "lineChart", "Upgrades vs. Downgrades by Plan", ("DimDate", "year_month"), ["Upgrade Events", "Downgrade Events"], 40, 585, 1200, 455, 4),
        _chart("age_bucket_col", "columnChart", "Subscription Age Distribution (Months)", ("DimSubscription", "age_months"), ["Active Subscriptions"], 1260, 585, 620, 455, 5),
    ]),
    ("live_activity_dashboard", "Live Activity Dashboard", [
        _card("live_kpis", ["Live Connected Subscriptions", "Live Active Sessions", "Live Idle Sessions", "Live Total Active Users", "Live Avg Session Duration Min", "Live API Requests/Hour"], 40, 25, 1840, 130, 0),
        _chart("live_status_donut", "donutChart", "Live Session Status Distribution", ("FactLiveActivity", "status"), ["Live Connected Subscriptions"], 40, 185, 540, 360, 1),
        _chart("live_feature_bar", "barChart", "Most Used Features Right Now", ("FactLiveActivity", "current_feature"), ["Live Connected Subscriptions"], 600, 185, 620, 360, 2),
        _chart("live_plan_col", "clusteredColumnChart", "Active Users by Plan", ("FactLiveActivity", "plan_name"), ["Live Total Active Users"], 1240, 185, 640, 360, 3),
        _table_visual("live_detail_table", "Live Subscription Activity Feed", [
            ("column", "FactLiveActivity", "subscription_id"), ("column", "FactLiveActivity", "plan_name"),
            ("column", "FactLiveActivity", "status"), ("column", "FactLiveActivity", "active_users"),
            ("column", "FactLiveActivity", "current_feature"), ("column", "FactLiveActivity", "session_duration_min"),
            ("column", "FactLiveActivity", "api_requests_last_hour"),
        ], 40, 575, 1300, 465, 4),
        _gauge("live_session_gauge", "Avg Session Duration", "Live Avg Session Duration Min", None, 1360, 575, 520, 225, 5),
        _multi_row_card("live_summary_card", "Live Platform Summary", ["Live Active Sessions", "Live Total Active Users", "Live API Requests/Hour"], 1360, 820, 520, 220, 6),
    ]),
    ("advanced_analytics", "Advanced Analytics & AI Insights", [
        _slicer("adv_slicer_region", "Region Filter", ("DimRegion", "region"), 40, 25, 300, 160, 0, "sync_region", mode="Vertical"),
        _chart("adv_kpi_trend", "lineChart", "Revenue Trend", ("DimDate", "year_month"), ["Monthly Revenue EUR"], 360, 25, 360, 160, 1),
        _multi_row_card("adv_summary_card", "Key Metrics Summary", ["Active Subscriptions", "Churn Rate %", "Average NPS Score", "Refund Amount EUR"], 740, 25, 740, 160, 2),
        _gauge("adv_nps_gauge", "NPS vs. Target", "Average NPS Score", "NPS Target", 1500, 25, 380, 160, 3),
        _anomaly_chart("anomaly_mrr", "Anomaly Detection: Revenue Trend", ("DimDate", "date"), "Monthly Revenue EUR", 40, 215, 900, 360, 4),
        _anomaly_chart("anomaly_tickets", "Anomaly Detection: Support Volume", ("DimDate", "date"), "Support Tickets", 960, 215, 900, 360, 5),
        _churn_by_segment("churn_decomp", "Churn Events by Segment & Plan", "Churn Events", [("DimAccount", "segment"), ("DimSubscription", "plan_name")], 40, 600, 1180, 440, 6),
        _churn_rate_by_plan("key_drivers_churn", "Churn Rate % by Plan", "Churn Rate %", [("DimSubscription", "plan_name")], 1240, 600, 640, 440, 7),
    ]),
    ("smart_narrative_overview", "Executive Narrative & Root Cause", [
        _card("narr_kpis", ["Active Subscriptions", "Total ARR EUR", "Churn Rate %", "Average NPS Score", "First Contact Resolution %"], 40, 25, 1840, 130, 0),
        _smart_narrative("smart_narr_revenue", "Revenue & Growth Story", ["Monthly Revenue EUR", "MRR MoM Growth %", "Expansion MRR EUR", "Contraction MRR EUR"], 40, 185, 880, 380, 1),
        _smart_narrative("smart_narr_support", "Support & Retention Insights", ["Support Tickets", "First Contact Resolution %", "Churn Rate %", "Average NPS Score"], 940, 185, 920, 380, 2),
        _matrix("root_cause_matrix", "Revenue Breakdown: Segment > Industry > Plan", [("DimAccount", "segment"), ("DimAccount", "industry"), ("DimSubscription", "plan_name")], ["Active Subscriptions", "Total ARR EUR", "Churn Rate %"], 40, 595, 1840, 445, 3),
    ]),
]


def build_model(source_kind: str, source_root: str) -> None:
    definition = MODEL_DIR / "definition"
    tables_dir = definition / "tables"
    if MODEL_DIR.exists():
        shutil.rmtree(MODEL_DIR)
    tables_dir.mkdir(parents=True)

    _write(MODEL_DIR / "definition.pbism", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {"qnaEnabled": True},
    })
    _write(definition / "database.tmdl", "database SaasPulse\n\tcompatibilityLevel: 1702\n\tcompatibilityMode: powerBI\n\tlanguage: 1033\n")
    refs = "\n".join(f"ref table {name}" for name in [*TABLES, MEASURE_TABLE])
    _write(definition / "model.tmdl", f"model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n\tsourceQueryCulture: en-US\n\n{refs}\n")
    _write(definition / "expressions.tmdl", _expressions_tmdl(source_kind, source_root))
    relationships = "\n\n".join(f"relationship '{name}'\n\tfromColumn: {source}\n\ttoColumn: {target}" for name, source, target in RELATIONSHIPS)
    _write(definition / "relationships.tmdl", relationships + "\n")
    for name, config in TABLES.items():
        _write(tables_dir / f"{name}.tmdl", _table_tmdl(name, config))
    _write(tables_dir / f"{MEASURE_TABLE}.tmdl", _measures_tmdl())


def build_report() -> None:
    if REPORT_DIR.exists():
        shutil.rmtree(REPORT_DIR)
    definition = REPORT_DIR / "definition"
    _write(POWERBI / f"{MODEL_NAME}.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{MODEL_NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    _write(REPORT_DIR / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{MODEL_NAME}.SemanticModel"}},
    })
    _write(definition / "version.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    theme_name = "Fluent2-CY26SU08"
    _write(definition / "report.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": theme_name, "reportVersionAtImport": {"visual": "2.12.0", "report": "3.4.0", "page": "2.3.1"}, "type": "SharedResources"}},
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources", "items": [{"name": theme_name, "path": f"BaseThemes/{theme_name}.json", "type": "BaseTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True, "useEnhancedTooltips": True},
    })
    legacy_pbix = POWERBI / "dashboard.pbix"
    if legacy_pbix.exists():
        member = f"Report/StaticResources/SharedResources/BaseThemes/{theme_name}.json"
        with zipfile.ZipFile(legacy_pbix) as archive:
            theme = archive.read(member)
        theme_path = REPORT_DIR / "StaticResources" / "SharedResources" / "BaseThemes" / f"{theme_name}.json"
        theme_path.parent.mkdir(parents=True, exist_ok=True)
        theme_path.write_bytes(theme)
    page_order = []
    for page_id, display_name, visuals in PAGES:
        page_order.append(page_id)
        page_dir = definition / "pages" / page_id
        _write(page_dir / "page.json", {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
            "name": page_id, "displayName": display_name, "displayOption": "FitToPage", "height": 1080, "width": 1920,
        })
        for visual in visuals:
            _write(page_dir / "visuals" / visual["name"] / "visual.json", visual)
    _write(definition / "pages" / "pages.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": page_order, "activePageName": page_order[0],
    })


def build_measure_catalog() -> None:
    lines = ["// Generated by scripts/build_powerbi_project.py. Do not edit manually.", ""]
    for name, expression, _ in MEASURES:
        lines.extend([f"{name} =", expression, ""])
    _write(POWERBI / "dax" / "measures.dax", "\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build source-controlled PBIP/TMDL/PBIR artifacts.")
    parser.add_argument("--source-kind", choices=("local", "azure-blob"), default="local")
    parser.add_argument("--source-root", help="Local data directory or Azure Blob container URL.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.source_root:
        source_root = args.source_root
    elif args.source_kind == "local":
        source_root = str((ROOT / "data").resolve())
    else:
        raise SystemExit("--source-root is required for azure-blob mode")
    build_model(args.source_kind, source_root.rstrip("/\\"))
    build_report()
    build_measure_catalog()
    print(f"Built {POWERBI / (MODEL_NAME + '.pbip')} using {args.source_kind} source {source_root}")


if __name__ == "__main__":
    main()
