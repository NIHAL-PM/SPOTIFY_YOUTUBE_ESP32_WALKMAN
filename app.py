import os
import threading
from flask import Flask, jsonify, request

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Core Config - Fallbacks keep things secure if environment vars take a moment to initialize
auth_manager = SpotifyOAuth(
    client_id=os.environ.get("SPOTIPY_CLIENT_ID"),
    client_secret=os.environ.get("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.environ.get("SPOTIPY_REDIRECT_URI"),
    scope="user-read-recently-played user-read-playback-state",
    open_browser=False,
)
sp = spotipy.Spotify(auth_manager=auth_manager)

# In-Memory Predictive Cache
next_track_cache = {"track": None, "artist": None, "stream_url": None, "ready": False}


def resolve_stream(artist, track_name):
    """Worker function to scrape raw audio URL fast"""
    search_query = f"ytsearch:{artist} {track_name} audio"
    ydl_opts = {
        "format": "ba[ext=m4a]/ba[ext=mp3]/bestaudio",
        "extract_flat": "discard_in_playlist",
        "skip_download": True,
        "quiet": True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            return info["entries"][0]["url"]
    except Exception:
        return None


def pre_cache_worker():
    """Background thread to look ahead into Spotify's algorithm"""
    global next_track_cache
    try:
        # Pull last played track to seed the recommendation matrix
        recent = sp.current_user_recently_played(limit=1)
        if not recent["items"]:
            return
        last_track_id = recent["items"][0]["track"]["id"]

        # Get 1 algorithmically recommended track from Spotify
        recs = sp.recommendations(seed_tracks=[last_track_id], limit=1)
        track = recs["tracks"][0]

        artist = track["artists"][0]["name"]
        title = track["name"]

        # Scrape streaming URL ahead of time
        url = resolve_stream(artist, title)

        if url:
            next_track_cache = {
                "track": title,
                "artist": artist,
                "stream_url": url,
                "ready": True,
            }
    except Exception as e:
        print(f"Pre-cache error: {e}")


# --- ADDED: HOMEPAGE ROUTE (To trigger authentication) ---
@app.route("/")
def index():
    try:
        token_info = auth_manager.cache_handler.get_cached_token()
        if not token_info or not auth_manager.validate_token(token_info):
            auth_url = auth_manager.get_authorize_url()
            return f'<h1>Walkman Auth Required</h1><p>Your backend server is active but not linked to Spotify yet.</p><a href="{auth_url}" style="padding:10px 20px;background:#1DB954;color:white;text-decoration:none;border-radius:20px;font-family:sans-serif;font-weight:bold;">Log into Spotify</a>'
        return "<h1>Walkman Status: Connected & Operational!</h1>"
    except Exception as e:
        return f"<h1>Initialization Error</h1><p>{str(e)}</p>"


# --- ADDED: CALLBACK ROUTE (Captures token securely from Spotify) ---
@app.route("/callback")
def callback():
    code = request.args.get("code")
    if code:
        auth_manager.get_access_token(code)
        # Immediately kick off the background thread to prime the cache
        threading.Thread(target=pre_cache_worker).start()
        return "<h1>Authentication Successful! Your token is locked in. You can close this tab now.</h1>"
    return "<h1>Authentication Failed. No authorization code received.</h1>", 400


@app.route("/control/next")
def get_next_track():
    global next_track_cache

    # 1. If cache is ready, instantly consume it
    if next_track_cache["ready"]:
        payload = {
            "track": next_track_cache["track"],
            "artist": next_track_cache["artist"],
            "stream_url": next_track_cache["stream_url"],
        }
        # Invalidate cache state immediately
        next_track_cache["ready"] = False
    else:
        # Fallback if skipped too fast before caching completed
        recent = sp.current_user_recently_played(limit=1)
        last_track_id = recent["items"][0]["track"]["id"]
        recs = sp.recommendations(seed_tracks=[last_track_id], limit=1)
        track = recs["tracks"][0]
        artist = track["artists"][0]["name"]
        title = track["name"]
        url = resolve_stream(artist, title)
        payload = {"track": title, "artist": artist, "stream_url": url}

    # 2. Fire up background thread to calculate the NEXT song instantly
    threading.Thread(target=pre_cache_worker).start()

    return jsonify(payload)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
