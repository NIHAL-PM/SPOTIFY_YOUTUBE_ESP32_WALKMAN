# SPOTIFY_YOUTUBE_ESP32_WALKMAN

A lightweight service that pre-fetches the next Spotify recommendation and resolves a playable stream URL (from YouTube) so low-powered clients — like an ESP32-based walkman — can play music with minimal latency.

Summary
-	Exposes a simple HTTP endpoint `/control/next` that returns JSON with `track`, `artist`, and a `stream_url` ready for playback.

Key features
-	Looks up your Spotify account's recent track and requests a Spotify recommendation.
-	Resolves a direct audio stream URL using `yt-dlp` so clients can play without transcoding or downloads.
-	Background pre-caching to reduce perceived skip latency.

Contents
-	[Requirements](#requirements)
-	[Quick start (local)](#quick-start-local)
-	[Run with Docker](#run-with-docker)
-	[Configuration / Environment variables](#configuration--environment-variables)
-	[API](#api)
-	[How it works](#how-it-works)
-	[ESP32 / low-power client integration notes](#esp32--low-power-client-integration-notes)
-	[Legal / Usage notes](#legal--usage-notes)
-	[Contributing](#contributing)
-	[License](#license)

Requirements
-	Python 3.10+ (tested with 3.11)
-	The Python dependencies are in `requirements.txt`:

```
Flask
spotipy
yt-dlp
gunicorn
```

Quick start (local)

1. Create a Python virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Create a Spotify Developer App at https://developer.spotify.com/dashboard and note the `Client ID` and `Client Secret`. Set a redirect URI (for example `http://localhost:5000/`) and add it to your app settings.

3. Export the required environment variables (see Configuration below). Example for a local run:

```bash
export SPOTIPY_CLIENT_ID=your_client_id
export SPOTIPY_CLIENT_SECRET=your_client_secret
export SPOTIPY_REDIRECT_URI=http://localhost:5000/
export PORT=5000
```

4. Run the server:

```bash
python app.py
```

5. Open `http://localhost:5000/control/next` in your browser or `curl` it to see the JSON response.

Run with Docker

Build the image (repository includes a `Dockerfile`):

```bash
docker build -t spotify-youtube-walkman .
```

Run the container, passing required env vars:

```bash
docker run -p 5000:5000 \
	-e SPOTIPY_CLIENT_ID=your_client_id \
	-e SPOTIPY_CLIENT_SECRET=your_client_secret \
	-e SPOTIPY_REDIRECT_URI=http://localhost:5000/ \
	spotify-youtube-walkman
```

Configuration / Environment variables
-	`SPOTIPY_CLIENT_ID` — Spotify Client ID
-	`SPOTIPY_CLIENT_SECRET` — Spotify Client Secret
-	`SPOTIPY_REDIRECT_URI` — Redirect URI configured in your Spotify app
-	`PORT` — Optional; HTTP server port (defaults to `5000`)

API
-	GET `/control/next`
	- Response JSON example:

```json
{
	"track": "Song Title",
	"artist": "Artist Name",
	"stream_url": "https://rX---.googlevideo.com/..."
}
```

How it works
-	When `/control/next` is requested the service will:
	- Attempt to return a previously pre-cached recommendation (fast path).
	- If no cache exists, query Spotify for a recommendation and resolve a playable URL using `yt-dlp`.
	- Spawn a background thread to pre-cache the NEXT recommendation for faster subsequent responses.

ESP32 / low-power client integration notes
-	This project is designed for constrained clients that can perform HTTP GET requests and play a remote stream URL.
-	Typical flow for an ESP32-based walkman:
	1. Make a GET request to `/control/next`.
	2. Parse the returned `stream_url` and play the audio stream using a streaming-capable audio library or an external decoder chip.
	3. When skipping, request `/control/next` again. The server attempts to make this near-instant by pre-caching.

Notes & limitations
-	`yt-dlp` is used to resolve YouTube-hosted audio streams. The URL returned may be short-lived.
-	This service does not host or re-distribute copyrighted content; it only resolves a direct media URL for client playback. Make sure your usage complies with Spotify and YouTube terms of service.
-	Rate limits and auth failures from Spotify can cause the endpoint to fail; production deployments should add retries, caching, and monitoring.

Contributing
-	Feel free to open issues or PRs to improve reliability, add unit tests, or provide ESP32 example client code.

License
-	This repository does not include a license file by default. Add a `LICENSE` if you want to make the project open-source.

Contact
-	For questions about setup or integrating an ESP32 client, open an issue or add a PR with your suggested improvements.
