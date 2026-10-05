# Power BI report

The build writes a small star schema to `outputs/powerbi/`:

| File | Grain | Columns |
|---|---|---|
| `fact_jolts_rates.csv` | industry x measure x month | date, industry_code, measure, rate |
| `fact_quits_forecast.csv` | industry x forecast month | date, industry_code, forecast, lower_80, upper_80, model |
| `dim_industry.csv` | industry | industry_code, industry, industry_short, level (Roll-up / Sector) |
| `dim_measure.csv` | measure | measure, measure_name |
| `dim_date.csv` | month | date, year, month, month_name, year_month, quarter |

## Build it

1. Power BI Desktop: **Get data > Text/CSV** and load the five files.
2. In Power Query, set `industry_code` to **Text** in every table (keeps `000000`), and `date` to **Date**.
3. Model view: create the relationships listed at the top of `measures.dax`.
4. Mark `dim_date` as the date table (`dim_date[date]`).
5. Add the measures from `measures.dax`.

## Pages

1. **Overview**: four KPI cards (Openings, Hires, Quits, Layoffs: latest 12M vs 2019),
   a line chart of the four rates over time for Total nonfarm, and a `Latest Month Label` card.
2. **Sectors**: bar chart of `Change vs 2019 %` for quits by `industry_short` (filter `level = Sector`),
   bar chart of `Openings per Hire`, and a matrix with all four rates per sector.
3. **Forecast**: line chart with `Quits Rate` (actual) and `Quits Forecast` plus the 80% band
   (`Quits Forecast Low 80` / `High 80` as an error band), with an industry slicer.

Refresh: run `python -m jolts fetch` then `python -m jolts build`, then **Refresh** in Power BI.
