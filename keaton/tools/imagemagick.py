import shutil
from .base import Tool


class ImageMagickTool(Tool):
    name = "imagemagick"
    binary = "magick" if shutil.which("magick") else "convert"
    category = "media"
    description = "Image manipulation: resize, crop, convert, optimise, watermark."
    install_hint = "Install: brew install imagemagick"
    keywords = ["image", "resize", "crop", "png", "jpg", "jpeg", "webp",
                "optimise", "optimize", "watermark", "transparent", "imagemagick"]
    capabilities = [
        "Resize / crop / convert", "Optimise & compress", "Transparency",
        "Colour correction", "Batch processing", "Watermarks", "Image compare",
    ]
    examples = [
        ("resize to 800px wide", "magick in.png -resize 800x out.png"),
        ("convert png to jpg", "magick in.png out.jpg"),
    ]
    recipes = {
        "resize": ["{input}", "-resize", "{size}", "{output}"],
        "convert": ["{input}", "{output}"],
    }
