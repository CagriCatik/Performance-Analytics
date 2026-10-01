let
    Source = Csv.Document(ReadProjectFile("raw/live_activity.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {
        {"subscription_id", type text}, {"account_id", type text}, {"plan_name", type text},
        {"status", type text}, {"active_users", Int64.Type}, {"max_users", Int64.Type},
        {"current_feature", type text}, {"session_duration_min", type number},
        {"api_requests_last_hour", Int64.Type}, {"last_updated", type datetimezone}
    }, "en-US"),
    Deduplicated = Table.Distinct(Types, {"subscription_id"})
in
    Deduplicated
