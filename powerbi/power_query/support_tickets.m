let
    Source = Csv.Document(ReadProjectFile("raw/support_tickets.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {
        {"ticket_id", type text}, {"subscription_id", type text}, {"account_id", type text},
        {"opened_at", type datetime}, {"closed_at", type text}, {"category", type text},
        {"severity", type text}, {"status", type text}, {"resolution_hours", type number},
        {"first_contact_resolution", type logical}, {"escalated", type logical},
        {"opened_date", type date}, {"country", type text}, {"region", type text},
        {"plan_name", type text}
    }, "en-US"),
    NormalizedCountry = Table.TransformColumns(Types, {{"country", NormalizeCountry}})
in
    NormalizedCountry
