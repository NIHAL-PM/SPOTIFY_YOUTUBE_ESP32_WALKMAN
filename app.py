import os
import threading
from flask import Flask, jsonify, request
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from yt_dlp import YoutubeDL

app = Flask(__name__)

auth_manager = SpotifyOAuth(
    client_id=os.environ.get("SPOTIPY_CLIENT_ID"),
    client_secret=os.environ.get("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.environ.get("SPOTIPY_REDIRECT_URI"),
    scope="user-top-read", # Changed scope to read top items (Free Tier friendly)
    open_browser=False
)
sp = spotipy.Spotify(auth_manager=auth_manager)

next_track_cache = {"track": None, "artist": None, "stream_url": None, "ready": False}

def resolve_stream(artist, track_name):
    search_query = f"ytsearch:{artist} {track_name} audio"
    ydl_opts = {
        'format': 'ba[ext=m4a]/ba[ext=mp3]/bestaudio',
        'extract_flat': 'discard_in_playlist',
        'skip_download': True,
        'quiet': True
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            return info['entries'][0]['url']
    except Exception:
        return None

def pre_cache_worker():
    global next_track_cache
    try:
        # --- FREE TIER WORKAROUND ---
        # Instead of live playback history, fetch one of your top tracks to seed recommendations
        try:
            top_tracks = sp.current_user_top_tracks(limit=1, time_range='medium_term')
            if top_tracks['items']:
                seed_track_id = top_tracks['items'][0]['id']
            else:
                raise ValueError("No top tracks found")
        except Exception:
            # Ultimate fallback: If the profile is brand new, use a generic lo-fi track ID as a seed
            seed_track_id = "0VjIjW4GlUZsz5dBZtZfsL" 
        
        recs = sp.recommendations(seed_tracks=[seed_track_id], limit=1)
        track = recs['tracks'][0]
        artist = track['artists'][0]['name']
        title = track['name']
        
        url = resolve_stream(artist, title)
        if url:
            next_track_cache = {
                "track": title,
                "artist": artist,
                "stream_url": url,
                "ready": True
            }
    except Exception as e:
        print(f"Pre-cache error: {e}")

@app.route('/')
def index():
    try:
        token_info = auth_manager.cache_handler.get_cached_token()
        if not token_info or not auth_manager.validate_token(token_info):
            auth_url = auth_manager.get_authorize_url()
            return f'<h1>Walkman Auth Required</h1><p>Free Tier Engine is ready.</p><a href="{auth_url}" style="padding:10px 20px;background:#1DB954;color:white;text-decoration:none;border-radius:20px;font-family:sans-serif;font-weight:bold;">Log into Spotify</a>'
        return "<h1>Walkman Status: Connected & Operational (Free Tier Mode)!</h1>"
    except Exception as e:
        return f"<h1>Initialization Error</h1><p>{str(e)}</p>"

@app.route('/callback')
def callback():
    code = request.args.get("code")
    if code:
        auth_manager.get_access_token(code)
        threading.Thread(target=pre_cache_worker).start()
        return "<h1>Authentication Successful! You can close this tab now.</h1>"
    return "<h1>Authentication Failed.</h1>", 400

@app.route('/control/next')
def get_next_track():
    global next_track_cache
    
    if next_track_cache["ready"]:
        payload = {
            "track": next_track_cache["track"],
            "artist": next_track_cache["artist"],
            "stream_url": next_track_cache["stream_url"]
        }
        next_track_cache["ready"] = False
    else:
        # Inline fallback logic matching the Free Tier seed structure
        try:
            top_tracks = sp.current_user_top_tracks(limit=1, time_range='medium_term')
            seed_track_id = top_tracks['items'][0]['id'] if top_tracks['items'] else "0VjIjW4GlUZsz5dBZtZfsL"
        except Exception:
            seed_track_id = "0VjIjW4GlUZsz5dBZtZfsL"

        recs = sp.recommendations(seed_tracks=[seed_track_id], limit=1)
        track = recs['tracks'][0]
        artist = track['artists'][0]['name']
        title = track['name']
        url = resolve_stream(artist, title)
        payload = {"track": title, "artist": artist, "stream_url": url}

    threading.Thread(target=pre_cache_worker).start()
    return jsonify(payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
