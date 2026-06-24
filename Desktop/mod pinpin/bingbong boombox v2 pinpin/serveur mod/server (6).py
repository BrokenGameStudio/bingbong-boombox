"""
Serveur Python pour télécharger des vidéos YouTube avec yt-dlp
Usage: python server.py
"""

import os
import sys
import shutil
import subprocess
import json
import re
import pathlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

# ─── Config ────────────────────────────────────────────────────────────────────

PORT = 8080
DOWNLOAD_DIR = "downloads"

_HERE = pathlib.Path(__file__).parent.resolve()

if sys.platform == "win32":
    YT_DLP_PATH = str(_HERE / "yt-dlp.exe")
else:
    # Linux / Termux : on cherche dans le PATH (pkg install yt-dlp)
    YT_DLP_PATH = shutil.which("yt-dlp") or "yt-dlp"

DOWNLOAD_DIR_ABS = str(_HERE / DOWNLOAD_DIR)

os.makedirs(DOWNLOAD_DIR_ABS, exist_ok=True)

# ─── Cache infos ─────────────────────────────────────────────────────────────────
_info_cache = {}

# ─── Helpers ───────────────────────────────────────────────────────────────────

def is_valid_youtube_url(url):
    pattern = r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]+"
    return bool(re.match(pattern, url))

def extract_video_id(url):
    """Extrait l'ID vidéo YouTube (ex: A0oLpAI3qqc) depuis n'importe quelle URL."""
    parsed = urlparse(url)
    # Format classique : youtube.com/watch?v=XXXXX
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    # Format court : youtu.be/XXXXX
    if parsed.netloc == "youtu.be":
        return parsed.path.lstrip("/").split("/")[0]
    return None

def run_download(url, quality, only_audio):
    video_id = extract_video_id(url) or "video"
    output_template = DOWNLOAD_DIR_ABS + "/" + video_id + ".%(ext)s"

    # On télécharge toujours l'audio et on convertit en WAV
    cmd = [
        YT_DLP_PATH, url,
        "-o", output_template,
        "-x",                        # extraire l'audio
        "--audio-format", "wav",     # convertir en WAV
        "--audio-quality", "0",      # meilleure qualité
    ]

    # Sélection de la source audio selon la qualité choisie
    if quality == "f251":
        cmd += ["-f", "251"]
    elif quality == "720p" or quality == "480p":
        cmd += ["-f", "bestaudio"]
    # pour "best" et "audio only" : yt-dlp choisit automatiquement la meilleure source audio

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            wav_path = DOWNLOAD_DIR_ABS + "/" + video_id + ".wav"
            return {"success": True, "output": result.stdout, "file": wav_path}
        else:
            return {"success": False, "error": result.stderr or result.stdout}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout: téléchargement trop long."}
    except FileNotFoundError:
        return {"success": False, "error": "yt-dlp.exe introuvable. Placez-le dans le même dossier que server.py."}

def get_info(url):
    video_id = extract_video_id(url)
    if video_id and video_id in _info_cache:
        return _info_cache[video_id]

    cmd = [YT_DLP_PATH, "--dump-json", "--no-playlist", "--no-warnings", "--socket-timeout", "10", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            info = {
                "success":   True,
                "title":     data.get("title", ""),
                "duration":  data.get("duration_string", ""),
                "uploader":  data.get("uploader", ""),
                "thumbnail": data.get("thumbnail", ""),
            }
            if video_id:
                _info_cache[video_id] = info
            return info
        return {"success": False, "error": result.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── HTML ──────────────────────────────────────────────────────────────────────

HTML = b"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YouTube Downloader</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f0f0f; color: #f1f1f1;
         display: flex; justify-content: center; padding: 40px 16px; }
  .card { background: #1e1e1e; border-radius: 12px; padding: 32px;
          width: 100%; max-width: 560px; box-shadow: 0 4px 24px #0008; }
  h1 { font-size: 1.5rem; margin-bottom: 24px; }
  label { font-size: .85rem; color: #aaa; display: block; margin-bottom: 6px; margin-top: 16px; }
  input[type=url], select { width: 100%; padding: 10px 14px; border-radius: 8px;
    border: 1px solid #333; background: #111; color: #f1f1f1; font-size: 1rem; outline: none; }
  input[type=url]:focus, select:focus { border-color: #f00; }
  .check-row { display: flex; align-items: center; gap: 8px; margin-top: 16px; }
  button { margin-top: 16px; width: 100%; padding: 12px; background: #f00; border: none;
           border-radius: 8px; color: #fff; font-size: 1rem; font-weight: 600;
           cursor: pointer; transition: background .2s; }
  button:hover { background: #c00; }
  button:disabled { background: #555; cursor: not-allowed; }
  #status { margin-top: 20px; padding: 14px; border-radius: 8px; font-size: .9rem;
            display: none; white-space: pre-wrap; word-break: break-word; }
  .ok      { background: #1a3a1a; border: 1px solid #2a6a2a; color: #7fff7f; }
  .err     { background: #3a1a1a; border: 1px solid #6a2a2a; color: #ff9090; }
  .loading { background: #1a2a3a; border: 1px solid #2a4a6a; color: #90c0ff; }
  #info-box { margin-top: 16px; padding: 12px; border-radius: 8px; background: #111;
              border: 1px solid #333; display: none; font-size: .85rem; }
  #info-box img { width: 100%; border-radius: 6px; margin-bottom: 8px; }
</style>
</head>
<body>
<div class="card">
  <h1>&#9654; YouTube Downloader</h1>

  <label for="url">URL YouTube</label>
  <input id="url" type="url" placeholder="https://www.youtube.com/watch?v=..." />

  <label for="quality">Qualite video</label>
  <select id="quality">
    <option value="f251">f251 - Audio WebM/Opus (recommande)</option>
    <option value="best">Meilleure qualite (video+audio)</option>
    <option value="720p">720p</option>
    <option value="480p">480p</option>
  </select>

  <div class="check-row">
    <input type="checkbox" id="audio-only">
    <label for="audio-only" style="margin:0">Audio seulement (MP3)</label>
  </div>

  <button id="info-btn">Voir les infos</button>
  <div id="info-box"></div>
  <button id="dl-btn">Telecharger</button>
  <div id="status"></div>
</div>

<script>
  function showStatus(msg, type) {
    var el = document.getElementById('status');
    el.textContent = msg;
    el.className = type;
    el.style.display = 'block';
  }

  function showInfo(data) {
    if (data.success) {
      document.getElementById('status').style.display = 'none';
      var box = document.getElementById('info-box');
      box.innerHTML = (data.thumbnail ? '<img src="' + data.thumbnail + '">' : '')
        + '<strong>' + data.title + '</strong><br>'
        + (data.uploader || '?') + ' &mdash; ' + (data.duration || '?');
      box.style.display = 'block';
    } else {
      showStatus('Erreur: ' + data.error, 'err');
    }
  }

  var _lastPrefetchUrl = '';
  var _prefetchTimer = null;

  // Des que l'utilisateur colle ou tape une URL, on lance le prefetch en arriere-plan
  document.getElementById('url').addEventListener('input', function() {
    var url = this.value.trim();
    if (!url || url === _lastPrefetchUrl) return;
    clearTimeout(_prefetchTimer);
    _prefetchTimer = setTimeout(function() {
      if (url.indexOf('youtube.com') === -1 && url.indexOf('youtu.be') === -1) return;
      _lastPrefetchUrl = url;
      fetch('/info?url=' + encodeURIComponent(url))
        .then(function(r) { return r.json(); })
        .then(function(data) {
          // On affiche seulement si l'URL n'a pas change entre temps
          if (document.getElementById('url').value.trim() === url) showInfo(data);
        })
        .catch(function() {});
    }, 600); // attend 600ms que l'utilisateur finisse de coller
  });

  document.getElementById('info-btn').addEventListener('click', function() {
    var url = document.getElementById('url').value.trim();
    if (!url) { showStatus('Entrez une URL.', 'err'); return; }
    // Si le prefetch est deja en cache cote serveur, ca repondra instantanement
    showStatus('Recuperation des infos...', 'loading');
    document.getElementById('info-box').style.display = 'none';
    fetch('/info?url=' + encodeURIComponent(url))
      .then(function(r) { return r.json(); })
      .then(showInfo)
      .catch(function(e) { showStatus('Erreur reseau: ' + e, 'err'); });
  });

  document.getElementById('dl-btn').addEventListener('click', function() {
    var url     = document.getElementById('url').value.trim();
    var quality = document.getElementById('quality').value;
    var audio   = document.getElementById('audio-only').checked;
    if (!url) { showStatus('Entrez une URL.', 'err'); return; }
    showStatus('Telechargement en cours...', 'loading');
    document.getElementById('dl-btn').disabled = true;
    fetch('/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url, quality: quality, audio_only: audio })
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.success) {
          showStatus('Telechargement termine !', 'ok');
        } else {
          showStatus('Erreur: ' + (data.error || 'Inconnue'), 'err');
        }
        document.getElementById('dl-btn').disabled = false;
      })
      .catch(function(e) {
        showStatus('Erreur reseau: ' + e, 'err');
        document.getElementById('dl-btn').disabled = false;
      });
  });
</script>
</body>
</html>
"""

# ─── Handler HTTP ──────────────────────────────────────────────────────────────

_NET_ERRORS = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Gère chaque requête dans un thread séparé."""
    daemon_threads = True

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print("[%s] %s" % (self.client_address[0], format % args))

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # Preflight CORS
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(HTML)))
                self.end_headers()
                self.wfile.write(HTML)
            elif parsed.path == "/info":
                params = parse_qs(parsed.query)
                url = params.get("url", [""])[0]
                if not url or not is_valid_youtube_url(url):
                    self.send_json({"success": False, "error": "URL invalide."}, 400)
                else:
                    self.send_json(get_info(url))
            elif parsed.path.startswith("/file/"):
                video_id = parsed.path[len("/file/"):]
                # Sécurité : caractères autorisés uniquement
                if not re.match(r'^[\w\-]+$', video_id):
                    self.send_json({"success": False, "error": "ID invalide."}, 400)
                    return
                wav_path = os.path.join(DOWNLOAD_DIR_ABS, video_id + ".wav")
                if not os.path.isfile(wav_path):
                    self.send_json({"success": False, "error": "Fichier introuvable : " + video_id + ".wav"}, 404)
                    return
                file_size = os.path.getsize(wav_path)
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(file_size))
                self.send_header("Content-Disposition", 'attachment; filename="' + video_id + '.wav"')
                self.end_headers()
                with open(wav_path, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            else:
                self.send_response(404)
                self.end_headers()
        except _NET_ERRORS:
            pass

    def do_POST(self):
        try:
            if self.path == "/download":
                length = int(self.headers.get("Content-Length", 0))
                try:
                    body = json.loads(self.rfile.read(length))
                except Exception:
                    self.send_json({"success": False, "error": "JSON invalide."}, 400)
                    return
                url        = body.get("url", "").strip()
                quality    = body.get("quality", "best")
                audio_only = bool(body.get("audio_only", False))
                if not url or not is_valid_youtube_url(url):
                    self.send_json({"success": False, "error": "URL YouTube invalide."}, 400)
                    return
                self.send_json(run_download(url, quality, audio_only))
            else:
                self.send_response(404)
                self.end_headers()
        except _NET_ERRORS:
            pass

# ─── Démarrage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import socket
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "?.?.?.?"

    local_ip = get_local_ip()
    server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
    print("=" * 50)
    print("Serveur demarre !")
    print("  Local    : http://localhost:%d" % PORT)
    print("  Reseau   : http://%s:%d" % (local_ip, PORT))
    print("=" * 50)
    print("yt-dlp path: %s" % YT_DLP_PATH)
    print("Existe:", os.path.exists(YT_DLP_PATH))
    print("Videos sauvegardees dans : ./%s/" % DOWNLOAD_DIR)
    print("Ctrl+C pour arreter.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServeur arrete.")
