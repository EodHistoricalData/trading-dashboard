import json
import asyncio
import httpx
from django.conf import settings
from datetime import datetime, timedelta
import requests
from django.shortcuts import render, get_object_or_404, redirect
from .models import SPGlobalIndex, IndexConstituent, HistoricalMarketData, SearchData


def fetch_data(request):
    api_token = settings.EODHD_API_TOKEN
    url = f"https://eodhd.com/api/mp/unicornbay/spglobal/list?api_token={api_token}"
    print(url)
    response = requests.get(url)
    data = response.json()

    for item in data:
        SPGlobalIndex.objects.update_or_create(
            index_id=item.get("ID"),
            defaults={
                "code": item.get("Code"),
                "name": item.get("Name"),
                "constituents": item.get("Constituents"),
                "value": item.get("Value"),
                "market_cap": item.get("MarketCap"),
                "divisor": item.get("Divisor"),
                "daily_return": item.get("DailyReturn"),
                "dividend": item.get("Dividend"),
                "adjusted_market_cap": item.get("AdjustedMarketCap"),
                "adjusted_divisor": item.get("AdjustedDivisor"),
                "adjusted_constituents": item.get("AdjustedConstituents"),
                "currency_code": item.get("CurrencyCode"),
                "currency_name": item.get("CurrencyName"),
                "currency_symbol": item.get("CurrencySymbol"),
                "last_update": item.get("LastUpdate"),
            },
        )

    indices = SPGlobalIndex.objects.all()
    return render(request, "spglobal/index.html", {"indices": indices})


def fetch_index_constituents(request, index_code):
    api_token = settings.EODHD_API_TOKEN
    url = f"https://eodhd.com/api/mp/unicornbay/spglobal/comp/{index_code}?fmt=json&api_token={api_token}"
    print(url)
    response = requests.get(url)
    data = response.json()

    constituents = data["Components"].values()
    general_info = data["General"]

    return render(
        request,
        "spglobal/constituents.html",
        {"constituents": constituents, "general_info": general_info},
    )


def rename_timestamp_field(data, interval):
    if interval in ("m", "w", "d"):
        for item in data:
            if "date" in item:
                item["timestamp"] = item.pop("date")
    else:
        for item in data:
            if "datetime" in item:
                item["timestamp"] = item.pop("datetime")
    return data


async def fetch_historical_data(request, market, interval):
    now = datetime.now()

    if interval in ["m", "w", "d"]:
        end_date = now.date().isoformat()
        start_date = (now - timedelta(days=300)).date().isoformat()
    else:
        end_date = now.strftime("%Y-%m-%dT%H:%M")
        start_date = (now - timedelta(hours=300)).strftime("%Y-%m-%dT%H:%M")

    start_date = request.GET.get("from", start_date)
    end_date = request.GET.get("to", end_date)

    def parse_datetime(dt_str):
        try:
            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            try:
                return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                return datetime.strptime(dt_str, "%Y-%m-%d")

    start_date_parsed = parse_datetime(start_date)
    end_date_parsed = parse_datetime(end_date)

    if interval in ["m", "w", "d"]:
        start_date = start_date_parsed.strftime("%Y-%m-%d")
        end_date = end_date_parsed.strftime("%Y-%m-%d")
    else:
        start_date_unix = int(start_date_parsed.timestamp())
        end_date_unix = int(end_date_parsed.timestamp())

    endpoint = "eod" if interval in ["m", "w", "d"] else "intraday"
    interval_type = "period" if interval in ["m", "w", "d"] else "interval"

    historical_url = (
        f"https://eodhd.com/api/{endpoint}/{market}?"
        f"{interval_type}={interval}&from={start_date if interval in ['m', 'w', 'd'] else start_date_unix}"
        f"&to={end_date if interval in ['m', 'w', 'd'] else end_date_unix}"
        f"&api_token={settings.EODHD_API_TOKEN}&fmt=json"
    )
    fundamental_url = f"https://eodhd.com/api/fundamentals/{market}?api_token={settings.EODHD_API_TOKEN}&fmt=json"

    today_minus_7_days = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    ohlc_url = (
        f"https://eodhd.com/api/eod/{market}?"
        f"period=d&from={today_minus_7_days}"
        f"&api_token={settings.EODHD_API_TOKEN}&fmt=json"
    )

    market_cap_url = f"https://eodhd.com/api/historical-market-cap/{market}?api_token={settings.EODHD_API_TOKEN}&fmt=json"

    async def fetch_data(url):
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.json()

    historical_data, fundamental_data, ohlc_data, market_cap_data = await asyncio.gather(
        fetch_data(historical_url),
        fetch_data(fundamental_url),
        fetch_data(ohlc_url),
        fetch_data(market_cap_url),
    )

    print(fundamental_url)

    # Process historical data
    def format_unix_timestamp(unix_ts):
        return datetime.utcfromtimestamp(unix_ts).strftime("%Y-%m-%d %H:%M:%S")

    for entry in historical_data:
        if "date" in entry:
            entry["timestamp"] = entry.pop("date")
        elif "datetime" in entry:
            datetime_value = entry.pop("datetime")
            try:
                entry["timestamp"] = format_unix_timestamp(int(datetime_value))
            except ValueError:
                entry["timestamp"] = datetime_value

    if not historical_data or "error" in historical_data:
        historical_data = []

    raw_data = historical_data
    historical_data_json = json.dumps(historical_data)

    # Process OHLC data
    ohlc_latest = {}
    if ohlc_data and len(ohlc_data) >= 2:
        latest_entry = ohlc_data[-1]
        second_last_entry = ohlc_data[-2]
        ohlc_latest = {
            "Open": latest_entry.get("open", "-"),
            "High": latest_entry.get("high", "-"),
            "Low": latest_entry.get("low", "-"),
            "Close": latest_entry.get("close", "-"),
            "Volume": latest_entry.get("volume", "-"),
            "Prev_Close": second_last_entry.get("close", "-"),
        }

    # Process fundamental data
    name = fundamental_data.get("General", {}).get("Name", "Unknown Company")
    description = fundamental_data.get("General", {}).get("Description", "-")
    highlights = fundamental_data.get("Highlights", {})
    technicals = fundamental_data.get("Technicals", {})
    shares_stats = fundamental_data.get("SharesStats", {})

    financials = fundamental_data.get("Financials", {})
    cash_flow = financials.get("Cash_Flow", {})  # dividendsPaid
    cash_flow_quarterly = cash_flow.get("quarterly", {})

    dividends_paid = [
        {"date": value.get("date"), "value": value.get("dividendsPaid", 0) or 0}
        for value in cash_flow_quarterly.values()
    ]
    dividends_paid = sorted(dividends_paid, key=lambda x: x["date"])
    dividends_paid_json = json.dumps(dividends_paid)

    earnings = fundamental_data.get("Earnings", {})
    earnings_history = earnings.get("History", {})  # epsActual

    eps_actual = [
        {"date": value.get("reportDate"), "value": value.get("epsActual", 0) or 0}
        for value in earnings_history.values()
    ]
    eps_actual = sorted(eps_actual, key=lambda x: x["date"])
    eps_actual_json = json.dumps(eps_actual)

    table_data = {
        "Prev_Close": "-",
        "Volume": "-",
        "Low": "-",
        "Market_Cap": highlights.get("MarketCapitalization", "-"),
        "Shares_Outstanding": shares_stats.get("SharesOutstanding", "-"),
        "EPS": highlights.get("EarningsShare", "-"),
        "Beta": technicals.get("Beta", "-"),
        "Open": "-",
        "High": "-",
        "52_wk_Range": f"{technicals.get('52WeekLow', '-')} - {technicals.get('52WeekHigh', '-')}",
        "PE_Ratio": highlights.get("PERatio", "-"),
        "Revenue": highlights.get("RevenueTTM", "-"),
        "Dividends_Yield": highlights.get("DividendYield", "-"),
    }

    market_cap = [
        {"date": entry["date"], "value": entry["value"]}
        for entry in market_cap_data.values()
    ]

    market_cap_json = json.dumps(market_cap, indent=4)

    return render(
        request,
        "historical/historical_data.html",
        {
            "market": market,
            "interval": interval,
            "historical_data": raw_data,  # Raw Python data for the table
            "historical_data_json": historical_data_json,  # JSON for the script
            "fundamental_name": name,
            "fundamental_description": description,
            "fundamental_table": table_data,
            "dividends_paid_json": dividends_paid_json,
            "eps_actual_json": eps_actual_json,
            "ohlc_latest": ohlc_latest,
            "market_cap_json": market_cap_json,
            "start_date": (
                start_date
                if interval in ["m", "w", "d"]
                else start_date_parsed.strftime("%Y-%m-%dT%H:%M")
            ),
            "end_date": (
                end_date
                if interval in ["m", "w", "d"]
                else end_date_parsed.strftime("%Y-%m-%dT%H:%M")
            ),
        },
    )


def search_market_data(request):
    query = request.GET.get("query", "")
    api_token = settings.EODHD_API_TOKEN
    url = f"https://eodhd.com/api/search/{query}?api_token={api_token}&fmt=json"

    response = requests.get(url)
    data = response.json() if response.status_code == 200 else []

    results = [SearchData(**item) for item in data]

    return render(
        request, "spglobal/search_results.html", {"results": results, "query": query}
    )
