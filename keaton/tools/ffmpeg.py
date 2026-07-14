from .base import Tool


class FFmpegTool(Tool):
    name = "ffmpeg"
    binary = "ffmpeg"
    category = "media"
    description = "Audio/video Swiss-army knife: convert, compress, trim, resize."
    install_hint = "Install: brew install ffmpeg  (or apt/choco install ffmpeg)"
    keywords = ["video", "audio", "compress", "convert", "trim", "clip", "merge",
                "gif", "mp4", "mp3", "resize", "crop", "rotate", "subtitle",
                "thumbnail", "frame", "loop", "encode", "ffmpeg"]
    capabilities = [
        "Compress / convert / resize / crop / rotate",
        "Trim, split, merge", "Extract or convert audio", "Audio normalization",
        "GIF creation", "Subtitle embed/extract", "Frame & thumbnail extraction",
        "Instagram / YouTube / TikTok presets", "Loop generation", "Metadata",
    ]
    examples = [
        ("compress this video", "ffmpeg -i in.mp4 -vcodec libx264 -crf 28 out.mp4"),
        ("convert to mp3", "ffmpeg -i in.mp4 -q:a 0 -map a out.mp3"),
        ("trim first 10 seconds", "ffmpeg -i in.mp4 -ss 0 -t 10 -c copy clip.mp4"),
        ("make a gif", "ffmpeg -i in.mp4 -vf fps=12,scale=480:-1 out.gif"),
        ("resize to 720p", "ffmpeg -i in.mp4 -vf scale=-2:720 out720.mp4"),
    ]
    recipes = {
        "compress": ["-i", "{input}", "-vcodec", "libx264", "-crf", "28", "{output}"],
        "to-audio": ["-i", "{input}", "-q:a", "0", "-map", "a", "{output}"],
        "trim":     ["-i", "{input}", "-ss", "{start}", "-t", "{dur}", "-c", "copy", "{output}"],
        "gif":      ["-i", "{input}", "-vf", "fps=12,scale=480:-1", "{output}"],
        "resize":   ["-i", "{input}", "-vf", "scale=-2:{height}", "{output}"],
    }
