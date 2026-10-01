let
    Source = Csv.Document(ReadProjectFile("raw/accounts.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {
        {"account_id", type text}, {"account_name", type text}, {"country", type text},
        {"region", type text}, {"city", type text}, {"latitude", type number},
        {"longitude", type number}, {"segment", type text}, {"industry", type text}
    }, "en-US"),
    NormalizedCountry = Table.TransformColumns(Types, {{"country", NormalizeCountry}}),
    Deduplicated = Table.Distinct(NormalizedCountry, {"account_id"})
in
    Deduplicated
