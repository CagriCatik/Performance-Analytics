let
    Source = Csv.Document(ReadProjectFile("reference/plans_catalog.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {
        {"plan_name", type text}, {"tier", type text}, {"monthly_price_eur", type number},
        {"annual_price_eur", type number}, {"max_users", Int64.Type}, {"churn_base", type number}
    }, "en-US")
in
    Types
