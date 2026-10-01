let
    Source = Csv.Document(ReadProjectFile("raw/monthly_metrics.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {
        {"month_date", type date}, {"subscription_id", type text}, {"account_id", type text},
        {"plan_name", type text}, {"mrr_eur", type number}, {"active_users", Int64.Type},
        {"licensed_users", Int64.Type}, {"active_user_ratio", type number}, {"api_calls", Int64.Type},
        {"storage_gb", type number}, {"feature_adoption_pct", type number},
        {"nps_score", Int64.Type}, {"revenue_at_risk_eur", type number}
    }, "en-US")
in
    Types
