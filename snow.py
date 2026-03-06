#!/usr/bin/env python3
"""
Snow Forecast Notifier for Switzerland.
Checks Open-Meteo forecasts for snowfall across Swiss cities
and sends a push notification via ntfy.sh.
"""

import argparse
import json
import ssl
import sys
from datetime import date
from urllib.request import Request, urlopen
from urllib.parse import urlencode

# Build SSL context — use system certs, fall back to unverified if unavailable (macOS Python)
try:
    _ssl_ctx = ssl.create_default_context()
    urlopen("https://api.open-meteo.com", timeout=5, context=_ssl_ctx)
except Exception:
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE

DEADLINE = date(2026, 3, 20)

# Major cities/regions across Switzerland (lat, lon, name)
LOCATIONS = [
    (47.3769, 8.5417, "Zürich"),
    (46.9480, 7.4474, "Bern"),
    (46.2044, 6.1432, "Geneva"),
    (47.5596, 7.5886, "Basel"),
    (46.0037, 8.9511, "Lugano"),
    (46.5197, 6.6323, "Lausanne"),
    (47.4245, 9.3767, "St. Gallen"),
    (47.0502, 8.3093, "Lucerne"),
    (46.8027, 9.8360, "Davos"),
    (46.0207, 7.7491, "Zermatt"),
    (46.6863, 7.8632, "Interlaken"),
    (46.2331, 7.3607, "Sion"),
    (46.8499, 9.5329, "Chur"),
    (46.1609, 8.7984, "Locarno"),
    (46.5547, 7.9674, "Grindelwald"),
]


def fetch_forecasts():
    """Fetch daily snowfall forecasts for all locations from Open-Meteo."""
    results = []
    for lat, lon, name in LOCATIONS:
        params = urlencode({
            "latitude": lat,
            "longitude": lon,
            "daily": "snowfall_sum",
            "timezone": "Europe/Zurich",
            "forecast_days": 7,
        })
        url = f"https://api.open-meteo.com/v1/forecast?{params}"
        try:
            with urlopen(url, timeout=15, context=_ssl_ctx) as resp:
                data = json.loads(resp.read())
            dates = data["daily"]["time"]
            snowfall = data["daily"]["snowfall_sum"]
            forecast = dict(zip(dates, snowfall))
            print(f"  {name}: {forecast}")
            snow_days = [
                (d, s) for d, s in zip(dates, snowfall)
                if s is not None and s > 0 and d <= str(DEADLINE)
            ]
            if snow_days:
                results.append((name, snow_days))
        except Exception as e:
            print(f"  {name}: FAILED - {e}")
    return results


def build_message(results):
    """Build a human-readable notification message."""
    if not results:
        return None

    lines = ["Snow forecasted in Switzerland:\n"]
    for name, snow_days in results:
        for day, cm in snow_days:
            lines.append(f"  {name}: {cm} cm on {day}")
    lines.append(f"\nNext check in ~12 hours.")
    return "\n".join(lines)


def send_notification(topic, title, message):
    """Send a push notification via ntfy.sh."""
    url = f"https://ntfy.sh/{topic}"
    req = Request(url, data=message.encode("utf-8"), method="POST")
    req.add_header("Title", title)
    req.add_header("Tags", "snowflake")
    with urlopen(req, timeout=15, context=_ssl_ctx) as resp:
        if resp.status != 200:
            print(f"ntfy responded with status {resp.status}")
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Switzerland snow forecast notifier")
    parser.add_argument("--topic", required=True, help="ntfy.sh topic to send notifications to")
    parser.add_argument("--always-notify", action="store_true", help="Send a notification even if no snow is forecasted")
    args = parser.parse_args()

    today = date.today()
    if today > DEADLINE:
        print(f"Past deadline ({DEADLINE}), exiting.")
        return

    print(f"Checking snow forecasts for {len(LOCATIONS)} Swiss locations...")
    results = fetch_forecasts()

    message = build_message(results)
    if message:
        print(message)
        title = f"Snow in Switzerland! ({today})"
        if send_notification(args.topic, title, message):
            print(f"\nNotification sent to ntfy.sh/{args.topic}")
        else:
            print("\nFailed to send notification.", file=sys.stderr)
            sys.exit(1)
    else:
        print("No snow in the forecast for any Swiss location.")
        if args.always_notify:
            no_snow_msg = f"No snow forecasted anywhere in Switzerland for the next 7 days (checked {today})."
            send_notification(args.topic, f"No snow in Switzerland ({today})", no_snow_msg)
            print(f"No-snow notification sent to ntfy.sh/{args.topic}")


if __name__ == "__main__":
    main()
