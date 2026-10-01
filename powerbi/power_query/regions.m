let
    Source = Csv.Document(ReadProjectFile("reference/regions.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {{"region", type text}, {"country", type text}, {"city", type text}, {"latitude", type number}, {"longitude", type number}}, "en-US"),
    Selected = Table.SelectColumns(Types, {"region"}),
    Trimmed = Table.TransformColumns(Selected, {{"region", Text.Trim, type text}}),
    Deduplicated = Table.Distinct(Trimmed, {"region"})
in
    Deduplicated
