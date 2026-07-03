# BingBongBoomBox

Mod **BepInEx** pour **PEAK** qui transforme le BingBong en enceinte capable de jouer de la musique YouTube (et autres plateformes), synchronisée pour tous les joueurs, avec un petit serveur Python en support pour le téléchargement/conversion audio.

## # Fonctionnalités

### Mod (BepInEx)
- Ouverture du lecteur en tenant un BingBong et en mettant le jeu en pause
- Lecture de liens YouTube, YouTube Shorts, SoundCloud, Bandcamp, Twitch (clips), Vimeo, TikTok, Mixcloud
- File d'attente avec shuffle / next / remove / clear, limites par utilisateur, et cache pour les relectures rapides
- Enqueue et contrôles publics activables (les non-détenteurs du BingBong peuvent ajouter des morceaux et utiliser les contrôles)
- Audio global (2D) ou positionnel 3D avec distance d'écoute réglable
- Affichage du titre en cours et du temps de lecture
- Fallback "acting-host" : fonctionne même si l'host n'a pas le mod
- Animation de bouche du BingBong synchronisée sur l'audio en cours (via détection FFT du spectre vocal)
- Configuration complète via BepInEx `ConfigEntry` (volume, taille de file, doublons, auto-advance, distance d'écoute, échelle UI, etc.), synchronisée aux autres joueurs par Photon

### Serveur (Python)
- Serveur HTTP local (`server.py`, port 8080 par défaut) qui télécharge et convertit l'audio via `yt-dlp` + `ffmpeg`
- Extraction et conversion en WAV, sélection de la qualité audio
- Cache des infos vidéo pour limiter les requêtes répétées
- Endpoints HTTP simples (GET/POST) consommés directement par le mod C#

## # Prérequis

- [BepInEx](https://github.com/BepInEx/BepInEx) installé sur PEAK
- .NET Standard 2.1 SDK pour compiler le mod
- Python 3 (ou l'exécutable embarqué fourni) pour lancer le serveur
- `yt-dlp.exe` et `ffmpeg.exe` (fournis dans `serveur mod/`)

## # Compilation du mod

```bash
dotnet build BingBongBoomBox.csproj
```

Le `.csproj` référence les DLL du jeu (`Assembly-CSharp`, `UnityEngine`, `PhotonUnityNetworking`, etc.) via `GameLibs/`.

## # Installation

1. Compiler le mod (ou récupérer `BingBongBoomBox.dll`)
2. Copier `BingBongBoomBox.dll` dans le dossier :
   ```
   PEAK/BepInEx/plugins/BingBongBoomBox/
   ```
3. Lancer le serveur Python (`server.py` ou l'exécutable fourni) sur la machine hôte
4. Renseigner l'URL du serveur (IP:port) dans la config du mod si besoin
5. Lancer le jeu, tenir un BingBong et mettre en pause pour ouvrir le lecteur

## # Notes

L'animation de bouche dépend d'un paramètre `float` de l'Animator dont le nom contient "mouth" sur le prefab du BingBong. Si ce paramètre disparaît dans une future mise à jour du jeu, l'animation ne fonctionnera plus jusqu'à correction.
