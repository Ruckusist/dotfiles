#!/usr/bin/env python3
"""
Polybar module for Google Antigravity ("antivirus") quota meters:
- 5-hour rolling usage period
- Weekly usage period
Matches the results of /usage from within the app with compact visual meters.
"""

import sys
import os
import json
import time
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

TOKEN_FILE = os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token")
CACHE_FILE = "/tmp/agy_quota_cache.json"
CACHE_TTL = 60  # seconds

SECRETS_FILE = os.path.expanduser("~/.config/polybar/antivirus_secrets.json")

CLIENT_ID = os.environ.get("AGY_CLIENT_ID", "")
CLIENT_SECRETS = [s for s in os.environ.get("AGY_CLIENT_SECRETS", "").split(",") if s]

if os.path.exists(SECRETS_FILE):
    try:
        with open(SECRETS_FILE, "r") as _sf:
            _sec_data = json.load(_sf)
            CLIENT_ID = _sec_data.get("client_id", CLIENT_ID)
            CLIENT_SECRETS = _sec_data.get("client_secrets", CLIENT_SECRETS)
    except Exception:
        pass

API_ENDPOINTS = [
    "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary",
    "https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary",
]

# Polybar theme colors (matching ~/.config/polybar/config.ini)
COLOR_PRIMARY = "#F0C674"
COLOR_SECONDARY = "#8ABEB7"
COLOR_ALERT = "#A54242"
COLOR_DISABLED = "#707880"
COLOR_FOREGROUND = "#C5C8C6"

# Meter characters:
# Option 1: ▰ and ▱ (smooth rectangles)
# Option 2: ■ and □ (squares)
# Option 3: █ and ░ (blocks)
METER_FILLED = "■"
METER_EMPTY = "□"
METER_WIDTH = 5


def get_stored_token_info():
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def refresh_access_token(token_info):
    refresh_token = token_info.get("token", {}).get("refresh_token")
    if not refresh_token:
        return None

    for secret in CLIENT_SECRETS:
        post_data = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "client_secret": secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=post_data,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                new_token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)

                token_info["token"]["access_token"] = new_token
                new_expiry = datetime.now(timezone.utc).timestamp() + expires_in
                token_info["token"]["expiry"] = datetime.fromtimestamp(new_expiry, timezone.utc).isoformat()

                try:
                    with open(TOKEN_FILE, "w") as f:
                        json.dump(token_info, f, indent=2)
                except Exception:
                    pass

                return new_token
        except Exception:
            continue
    return None


def get_valid_access_token():
    token_info = get_stored_token_info()
    if not token_info:
        return None

    token_data = token_info.get("token", {})
    access_token = token_data.get("access_token")
    expiry_str = token_data.get("expiry")

    is_expired = False
    if expiry_str:
        try:
            clean_expiry = expiry_str.split(".")[0].rstrip("Z")
            exp_dt = datetime.fromisoformat(clean_expiry).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc).timestamp() >= (exp_dt.timestamp() - 60):
                is_expired = True
        except Exception:
            pass

    if is_expired or not access_token:
        new_token = refresh_access_token(token_info)
        if new_token:
            return new_token

    return access_token


def fetch_quota_from_api():
    access_token = get_valid_access_token()
    if not access_token:
        return None

    for endpoint in API_ENDPOINTS:
        req = urllib.request.Request(
            endpoint,
            data=b"{}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "AntigravityCLI",
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "groups" in data:
                    return data
        except urllib.error.HTTPError as e:
            if e.code == 401:
                token_info = get_stored_token_info()
                if token_info:
                    new_token = refresh_access_token(token_info)
                    if new_token:
                        req.headers["Authorization"] = f"Bearer {new_token}"
                        try:
                            with urllib.request.urlopen(req, timeout=5) as retry_resp:
                                return json.loads(retry_resp.read().decode("utf-8"))
                        except Exception:
                            pass
            continue
        except Exception:
            continue
    return None


def get_cached_quota(force_refresh=False):
    now = time.time()
    if not force_refresh and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cached = json.load(f)
            cache_time = cached.get("_cache_time", 0)
            if now - cache_time < CACHE_TTL:
                return cached.get("data")
        except Exception:
            pass

    data = fetch_quota_from_api()
    if data:
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump({"_cache_time": now, "data": data}, f)
        except Exception:
            pass
        return data

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f).get("data")
        except Exception:
            pass
    return None


def parse_quota(quota_data):
    if not quota_data or "groups" not in quota_data:
        return None

    gemini_buckets = {}
    other_buckets = {}

    for group in quota_data.get("groups", []):
        display_name = group.get("displayName", "")
        buckets = group.get("buckets", [])
        target = gemini_buckets if "Gemini" in display_name else other_buckets

        for bucket in buckets:
            window = bucket.get("window")
            rem = bucket.get("remainingFraction", 1.0)
            reset_time = bucket.get("resetTime")
            desc = bucket.get("description", "")
            target[window] = {
                "remaining": rem,
                "percent": int(round(rem * 100)),
                "reset_time": reset_time,
                "description": desc,
            }

    return {"gemini": gemini_buckets, "other": other_buckets}


def format_remaining_time(reset_time_str):
    if not reset_time_str:
        return ""
    try:
        clean_time = reset_time_str.split(".")[0].rstrip("Z")
        reset_dt = datetime.fromisoformat(clean_time).replace(tzinfo=timezone.utc)
        diff = int((reset_dt - datetime.now(timezone.utc)).total_seconds())
        if diff <= 0:
            return "ready"
        days = diff // 86400
        hours = (diff % 86400) // 3600
        mins = (diff % 3600) // 60
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {mins}m"
        else:
            return f"{mins}m"
    except Exception:
        return ""


def build_meter(fraction, width=METER_WIDTH):
    filled = max(0, min(width, int(round(fraction * width))))
    empty = width - filled

    if fraction >= 0.5:
        bar_color = COLOR_PRIMARY
    elif fraction >= 0.2:
        bar_color = COLOR_SECONDARY
    else:
        bar_color = COLOR_ALERT

    filled_str = f"%{{F{bar_color}}}{METER_FILLED * filled}%{{F-}}"
    empty_str = f"%{{F{COLOR_DISABLED}}}{METER_EMPTY * empty}%{{F-}}"
    return f"{filled_str}{empty_str}"


def render_polybar(parsed):
    if not parsed or "gemini" not in parsed:
        return f"%{{F{COLOR_DISABLED}}}󰚩 N/A%{{F-}}"

    g = parsed["gemini"]
    b_5h = g.get("5h", {"remaining": 1.0, "percent": 100})
    b_wk = g.get("weekly", {"remaining": 1.0, "percent": 100})

    meter_5h = build_meter(b_5h["remaining"])
    meter_wk = build_meter(b_wk["remaining"])

    p5 = b_5h["percent"]
    pw = b_wk["percent"]

    return (
        f"%{{F{COLOR_PRIMARY}}}󰚩%{{F-}} "
        f"%{{F{COLOR_DISABLED}}}5h%{{F-}} {meter_5h} %{{F{COLOR_FOREGROUND}}}{p5}%%{{F-}}  "
        f"%{{F{COLOR_DISABLED}}}1w%{{F-}} {meter_wk} %{{F{COLOR_FOREGROUND}}}{pw}%%{{F-}}"
    )


def show_notification(parsed):
    if not parsed:
        subprocess.run(["notify-send", "-u", "normal", "Google Antigravity Quota", "Unable to retrieve quota."])
        return

    g = parsed.get("gemini", {})
    g_5h = g.get("5h", {})
    g_wk = g.get("weekly", {})

    t_5h = format_remaining_time(g_5h.get("reset_time"))
    t_wk = format_remaining_time(g_wk.get("reset_time"))

    body = [
        "<b>🛡️ Google Antigravity / Gemini Quota:</b>",
        f"• <b>5-Hour Limit:</b> {g_5h.get('percent', 100)}% remaining (resets in {t_5h})",
        f"• <b>Weekly Limit:</b> {g_wk.get('percent', 100)}% remaining (resets in {t_wk})",
    ]

    o = parsed.get("other", {})
    if o:
        o_5h = o.get("5h", {})
        o_wk = o.get("weekly", {})
        ot_5h = format_remaining_time(o_5h.get("reset_time"))
        ot_wk = format_remaining_time(o_wk.get("reset_time"))
        body.append("")
        body.append("<b>Claude & GPT Models:</b>")
        body.append(f"• <b>5-Hour Limit:</b> {o_5h.get('percent', 100)}% remaining (resets in {ot_5h})")
        body.append(f"• <b>Weekly Limit:</b> {o_wk.get('percent', 100)}% remaining (resets in {ot_wk})")

    subprocess.run([
        "notify-send",
        "-u", "normal",
        "-a", "Google Antigravity",
        "Google Antigravity Quota (/usage)",
        "\n".join(body)
    ])


def main():
    args = sys.argv[1:]

    if "--notify" in args:
        quota_data = get_cached_quota(force_refresh=False)
        parsed = parse_quota(quota_data)
        show_notification(parsed)
        return

    force_refresh = "--refresh" in args
    quota_data = get_cached_quota(force_refresh=force_refresh)
    parsed = parse_quota(quota_data)
    output = render_polybar(parsed)
    print(output)


if __name__ == "__main__":
    main()
