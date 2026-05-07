#!/usr/bin/env python3
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception


STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "")
STEAM_ID = os.environ.get("STEAM_ID", "")
PORT = int(os.environ.get("PORT", "8095"))
TZ_NAME = os.environ.get("TZ", "America/Los_Angeles")
RECENT_GAMES_LIMIT = int(os.environ.get("RECENT_GAMES_LIMIT", "50"))
RECENT_ACHIEVEMENT_SCAN_LIMIT = int(os.environ.get("RECENT_ACHIEVEMENT_SCAN_LIMIT", "20"))
RECENT_ACHIEVEMENT_DEADLINE_SECONDS = float(os.environ.get("RECENT_ACHIEVEMENT_DEADLINE_SECONDS", "8"))
HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "5"))
BASE = "https://api.steampowered.com"
USER_AGENT = "glance-steam-achievements/1.0"

_cache = {}


def pacific_tz_for_utc(utc_dt):
    year = utc_dt.year
    march_first = datetime(year, 3, 1, tzinfo=timezone.utc)
    first_march_sunday = 1 + ((6 - march_first.weekday()) % 7)
    second_march_sunday = first_march_sunday + 7
    dst_start_utc = datetime(year, 3, second_march_sunday, 10, tzinfo=timezone.utc)

    november_first = datetime(year, 11, 1, tzinfo=timezone.utc)
    first_november_sunday = 1 + ((6 - november_first.weekday()) % 7)
    dst_end_utc = datetime(year, 11, first_november_sunday, 9, tzinfo=timezone.utc)

    offset = -7 if dst_start_utc <= utc_dt < dst_end_utc else -8
    return timezone(timedelta(hours=offset), "America/Los_Angeles")


def configured_tz(utc_dt=None):
    utc_dt = utc_dt or datetime.now(timezone.utc)
    if ZoneInfo is not None:
        try:
            return ZoneInfo(TZ_NAME)
        except ZoneInfoNotFoundError:
            pass
    if TZ_NAME == "America/Los_Angeles":
        return pacific_tz_for_utc(utc_dt)
    return timezone.utc


def now_local():
    utc_now = datetime.now(timezone.utc)
    return utc_now.astimezone(configured_tz(utc_now))


def cache_get(key, ttl_seconds):
    item = _cache.get(key)
    if not item:
        return None
    expires_at, value = item
    if expires_at <= time.time():
        _cache.pop(key, None)
        return None
    return value


def cache_set(key, value, ttl_seconds):
    _cache[key] = (time.time() + ttl_seconds, value)
    return value


def get_json(url, ttl_seconds=900):
    cached = cache_get(("url", url), ttl_seconds)
    if cached is not None:
        return cached

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return cache_set(("url", url), payload, ttl_seconds)


def steam_url(path, **params):
    clean_params = {key: value for key, value in params.items() if value not in (None, "")}
    return f"{BASE}{path}?{urllib.parse.urlencode(clean_params)}"


def require_steam_config():
    if not STEAM_API_KEY or not STEAM_ID:
        raise ValueError("STEAM_API_KEY and STEAM_ID must be set")


def recent_games(limit=50):
    require_steam_config()
    url = steam_url(
        "/IPlayerService/GetRecentlyPlayedGames/v0001/",
        key=STEAM_API_KEY,
        steamid=STEAM_ID,
        count=limit,
        format="json",
    )
    return get_json(url, 900).get("response", {}).get("games", [])


def owned_games():
    require_steam_config()
    url = steam_url(
        "/IPlayerService/GetOwnedGames/v0001/",
        key=STEAM_API_KEY,
        steamid=STEAM_ID,
        include_appinfo="true",
        include_played_free_games="true",
        format="json",
    )
    return get_json(url, 21600).get("response", {}).get("games", [])


def player_achievements(appid):
    require_steam_config()
    url = steam_url(
        "/ISteamUserStats/GetPlayerAchievements/v0001/",
        key=STEAM_API_KEY,
        steamid=STEAM_ID,
        appid=appid,
        l="en",
        format="json",
    )
    data = get_json(url, 1800)
    stats = data.get("playerstats", {})
    if stats.get("success") is False:
        return []
    return stats.get("achievements", [])


def game_schema(appid):
    require_steam_config()
    url = steam_url(
        "/ISteamUserStats/GetSchemaForGame/v2/",
        key=STEAM_API_KEY,
        appid=appid,
        l="en",
        format="json",
    )
    data = get_json(url, 86400)
    achievements = data.get("game", {}).get("availableGameStats", {}).get("achievements", [])
    return {item.get("name"): item for item in achievements}


def achievement_url(appid, achievement_name):
    return f"https://steamcommunity.com/profiles/{STEAM_ID}/stats/{appid}/achievements"


def store_url(appid):
    return f"https://store.steampowered.com/app/{appid}/"


def achievement_record(game, achievement, schema_item=None):
    schema_item = schema_item or {}
    appid = int(game.get("appid", 0))
    api_name = achievement.get("apiname") or achievement.get("name") or schema_item.get("name", "")
    unlocktime = int(achievement.get("unlocktime", 0) or 0)
    unlocked_utc = datetime.fromtimestamp(unlocktime, tz=timezone.utc) if unlocktime else None
    unlocked_at = unlocked_utc.astimezone(configured_tz(unlocked_utc)) if unlocked_utc else None
    return {
        "appid": appid,
        "game_name": game.get("name") or game.get("gameName") or f"App {appid}",
        "achievement_name": api_name,
        "display_name": schema_item.get("displayName") or achievement.get("name") or api_name,
        "description": schema_item.get("description") or achievement.get("description") or "",
        "icon": schema_item.get("icon") or schema_item.get("icongray") or "",
        "icongray": schema_item.get("icongray") or schema_item.get("icon") or "",
        "unlocktime": unlocktime,
        "unlock_date": f"{unlocked_at.strftime('%b')} {unlocked_at.day}, {unlocked_at.year}" if unlocked_at else "",
        "store_url": store_url(appid),
        "achievement_url": achievement_url(appid, api_name),
    }


def get_recent_achievements(limit):
    cached = cache_get(("recent-achievements-v2", limit), 3600)
    if cached is not None:
        return cached

    started_at = time.monotonic()
    achievements = []
    games = [
        game
        for game in recent_games(RECENT_GAMES_LIMIT)
        if int(game.get("appid", 0) or 0) > 0 and int(game.get("playtime_forever", 0) or 0) > 0
    ]
    games.sort(key=lambda item: int(item.get("rtime_last_played", 0) or 0), reverse=True)

    for game in games[:RECENT_ACHIEVEMENT_SCAN_LIMIT]:
        if time.monotonic() - started_at >= RECENT_ACHIEVEMENT_DEADLINE_SECONDS:
            break

        oldest_kept_unlock = achievements[limit - 1]["unlocktime"] if len(achievements) >= limit else 0
        last_played = int(game.get("rtime_last_played", 0) or 0)
        if oldest_kept_unlock and last_played and last_played < oldest_kept_unlock:
            break

        appid = game.get("appid")
        try:
            unlocked = [
                achievement
                for achievement in player_achievements(appid)
                if int(achievement.get("achieved", 0) or 0) == 1
                and int(achievement.get("unlocktime", 0) or 0) > 0
            ]
            if not unlocked:
                continue

            schema = game_schema(appid)
            for achievement in unlocked:
                record = achievement_record(game, achievement, schema.get(achievement.get("apiname")))
                if record["unlocktime"] > 0:
                    achievements.append(record)
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
            continue

        achievements.sort(key=lambda item: item["unlocktime"], reverse=True)
        achievements = achievements[:limit]

    payload = {
        "generated_at": now_local().isoformat(),
        "achievements": achievements[:limit],
    }
    return cache_set(("recent-achievements-v2", limit), payload, 3600)


def week_window(now=None):
    now = now or now_local()
    this_monday = (now - timedelta(days=now.weekday())).replace(hour=6, minute=0, second=0, microsecond=0)
    if now < this_monday:
        this_monday -= timedelta(days=7)
    next_monday = this_monday + timedelta(days=7)
    return this_monday, next_monday


def get_weekly_challenge(count):
    starts_at, refreshes_at = week_window()
    cache_key = ("weekly-challenge-picks-v2", starts_at.isoformat(), count)
    cached = cache_get(cache_key, max(60, int((refreshes_at - now_local()).total_seconds())))
    if cached is None:
        games = [game for game in owned_games() if int(game.get("appid", 0) or 0) > 0]
        seed = f"{STEAM_ID}:{starts_at.date().isoformat()}:achievement-challenge"
        rng = random.Random(seed)
        rng.shuffle(games)

        challenges = []
        for game in games[:250]:
            if len(challenges) >= count:
                break
            appid = game.get("appid")
            try:
                schema = game_schema(appid)
                achievements = player_achievements(appid)
            except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
                continue

            locked = [
                achievement
                for achievement in achievements
                if int(achievement.get("achieved", 0) or 0) == 0
                and (achievement.get("apiname") or achievement.get("name")) in schema
            ]
            if not locked:
                continue
            achievement = rng.choice(locked)
            challenges.append(achievement_record(game, achievement, schema.get(achievement.get("apiname"))))

        cached = cache_set(cache_key, challenges, max(60, int((refreshes_at - now_local()).total_seconds())))

    challenges = []
    for challenge in cached:
        challenge = dict(challenge)
        challenge["completed"] = False
        try:
            for achievement in player_achievements(challenge["appid"]):
                api_name = achievement.get("apiname") or achievement.get("name")
                if api_name == challenge["achievement_name"] and int(achievement.get("achieved", 0) or 0) == 1:
                    challenge["completed"] = True
                    unlocktime = int(achievement.get("unlocktime", 0) or 0)
                    if unlocktime:
                        unlocked_utc = datetime.fromtimestamp(unlocktime, tz=timezone.utc)
                        unlocked_at = unlocked_utc.astimezone(configured_tz(unlocked_utc))
                        challenge["unlocktime"] = unlocktime
                        challenge["unlock_date"] = f"{unlocked_at.strftime('%b')} {unlocked_at.day}, {unlocked_at.year}"
                    break
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
            pass
        challenges.append(challenge)

    payload = {
        "week_starts_at": starts_at.isoformat(),
        "refreshes_at": refreshes_at.isoformat(),
        "challenges": challenges,
    }
    return payload


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/health":
                self.send_json(200, {"ok": True})
            elif parsed.path == "/recent-achievements":
                limit = min(25, max(1, int(query.get("limit", ["10"])[0])))
                self.send_json(200, get_recent_achievements(limit))
            elif parsed.path == "/weekly-challenge":
                count = min(10, max(1, int(query.get("count", ["3"])[0])))
                self.send_json(200, get_weekly_challenge(count))
            else:
                self.send_json(404, {"error": "not found"})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Steam achievements API listening on :{PORT}", flush=True)
    server.serve_forever()
