let
    Source = Csv.Document(ReadProjectFile("raw/subscription_events.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {
        {"event_id", type text}, {"subscription_id", type text}, {"account_id", type text},
        {"event_type", type text}, {"event_date", type date}, {"event_timestamp", type datetime},
        {"from_plan", type text}, {"to_plan", type text}, {"mrr_change_eur", type number},
        {"region", type text}, {"country", type text}
    }, "en-US"),
    NormalizedCountry = Table.TransformColumns(Types, {{"country", NormalizeCountry}})
in
    NormalizedCountry
