let
    Source = Csv.Document(ReadProjectFile("raw/subscriptions.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {
        {"subscription_id", type text}, {"account_id", type text}, {"plan_name", type text},
        {"plan_tier", type text}, {"billing_cycle", type text}, {"annual_value_eur", type number},
        {"mrr_eur", type number}, {"start_date", type date}, {"end_date", type text},
        {"status", type text}, {"age_months", Int64.Type}, {"max_users", Int64.Type},
        {"country", type text}, {"region", type text}
    }, "en-US"),
    NormalizedCountry = Table.TransformColumns(Types, {{"country", NormalizeCountry}}),
    Deduplicated = Table.Distinct(NormalizedCountry, {"subscription_id"})
in
    Deduplicated
