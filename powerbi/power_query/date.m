let
    Source = Csv.Document(ReadProjectFile("raw/monthly_metrics.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    DatesOnly = Table.TransformColumnTypes(Table.SelectColumns(Headers, {"month_date"}), {{"month_date", type date}}, "en-US"),
    MinDate = List.Min(DatesOnly[month_date]),
    MaxDate = List.Max(DatesOnly[month_date]),
    Calendar = Table.FromList(List.Dates(MinDate, Duration.Days(MaxDate - MinDate) + 1, #duration(1, 0, 0, 0)), Splitter.SplitByNothing(), {"date"}),
    Typed = Table.TransformColumnTypes(Calendar, {{"date", type date}}),
    Year = Table.AddColumn(Typed, "year", each Date.Year([date]), Int64.Type),
    MonthNumber = Table.AddColumn(Year, "month_number", each Date.Month([date]), Int64.Type),
    Month = Table.AddColumn(MonthNumber, "month", each Date.ToText([date], "MMM", "en-US"), type text),
    YearMonth = Table.AddColumn(Month, "year_month", each Date.ToText([date], "yyyy-MM", "en-US"), type text),
    MonthStart = Table.AddColumn(YearMonth, "month_start", each Date.StartOfMonth([date]), type date),
    IsWorkingDay = Table.AddColumn(MonthStart, "is_working_day", each Date.DayOfWeek([date], Day.Monday) < 5, type logical)
in
    IsWorkingDay
