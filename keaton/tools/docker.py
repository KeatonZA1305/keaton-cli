from .base import Tool


class DockerTool(Tool):
    name = "docker"
    binary = "docker"
    category = "containers"
    description = "Build, run and manage containers, images, volumes and networks."
    install_hint = "Install Docker Desktop: https://docs.docker.com/get-docker/"
    keywords = ["docker", "container", "image", "build", "dockerfile", "compose",
                "volume", "network", "logs", "exec", "prune"]
    capabilities = [
        "Build images", "Run / stop containers", "Logs & exec", "Compose",
        "Networks & volumes", "Inspect", "Dockerfile generation", "Image cleanup",
    ]
    examples = [
        ("show running containers", "docker ps"),
        ("build an image tagged app", "docker build -t app ."),
        ("show logs for a container", "docker logs -f <container>"),
        ("clean up unused stuff", "docker system prune -f"),
    ]
    recipes = {
        "ps": ["ps"],
        "images": ["images"],
        "build": ["build", "-t", "{tag}", "{context}"],
        "logs": ["logs", "-f", "{container}"],
        "prune": ["system", "prune", "-f"],
    }
    destructive = {"prune", "rmi", "rm"}
