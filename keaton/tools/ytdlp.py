from .base import Tool


class YtDlpTool(Tool):
    name = "yt-dlp"
    binary = "yt-dlp"
    category = "media"
    description = "Download media (respecting each platform's terms of service)."
    install_hint = "Install: brew install yt-dlp  (or pipx install yt-dlp)"
    keywords = ["download", "yt-dlp", "youtube", "playlist", "subtitles",
                "audio extraction", "media download"]
    capabilities = [
        "Media download", "Playlist support", "Audio extraction",
        "Subtitle download", "Thumbnail & metadata", "Quality selection",
    ]
    examples = [
        ("download this video", "yt-dlp <url>"),
        ("just the audio", "yt-dlp -x --audio-format mp3 <url>"),
    ]
    recipes = {
        "download": ["{url}"],
        "audio": ["-x", "--audio-format", "mp3", "{url}"],
    }
