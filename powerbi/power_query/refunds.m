let
    Source = Csv.Document(ReadProjectFile("raw/refunds.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {
        {"refund_id", type text}, {"ticket_id", type text}, {"subscription_id", type text},
        {"account_id", type text}, {"claim_date", type date}, {"reason", type text},
        {"amount_eur", type number}, {"approved", type logical}, {"plan_name", type text},
        {"country", type text}, {"region", type text}
    }, "en-US"),
    NormalizedCountry = Table.TransformColumns(Types, {{"country", NormalizeCountry}})
in
    NormalizedCountry
