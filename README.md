# Keaton

**An AI operating system for your terminal.** You describe what you want to get
done, in plain English, and Keaton figures out *which* real developer tool can
do it. `ffmpeg`, `git`, `docker`, `kubectl`, `ripgrep`, `pandoc`, and a dozen
more. It shows you exactly what it is about to run, then gets out of your way.

Most CLIs make you memorise flags. Keaton does not. It is the difference between
*"what was the ffmpeg incantation for a GIF again?"* and just typing:

```bash
keaton run "turn this clip into a gif"
```

## Why people like it

* **You talk, it translates.** Natural language in, the right tool and the right
  command out. No more digging through man pages or Stack Overflow tabs.
* **It uses the *real* tools.** Keaton does not reinvent `git` or `ffmpeg`. It
  drives the official CLIs you already trust, so the output is exactly what you
  would get by hand.
* **Nothing happens behind your back.** Every command is printed before it runs.
  Anything destructive (dropping a database, a `terraform destroy`, pruning
  Docker) asks first, and there is a dry run mode for the cautious.
* **One brain, every tool.** Eighteen tools across video, containers, Kubernetes,
  infrastructure, databases, search, and documents, all behind one consistent,
  good looking interface.
* **Add a tool in one small file.** The architecture is modular. Drop a file in
  `keaton/tools/` and it is discovered automatically. No core changes, no
  registration boilerplate.
* **Bring your own AI.** Base44, OpenAI, Anthropic, Gemini, OpenRouter, Ollama,
  LM Studio, or a local model. Pick whichever you like.

## What it drives

* **Media:** FFmpeg, ImageMagick, and yt dlp
* **Version control:** Git
* **Containers and orchestration:** Docker, kubectl
* **Infrastructure:** Terraform
* **Languages:** Python, Node.js
* **System package managers:** Homebrew, apt, dnf, pacman, winget
* **Search:** ripgrep, fd
* **Data and documents:** jq, Pandoc
* **Databases:** SQLite, PostgreSQL, MySQL
* **Remote:** SSH, SCP, SFTP

Ask Keaton what it can do at any time:

```bash
keaton tools            # every tool, and whether it is installed
keaton tool ffmpeg      # capabilities and real examples for one tool
keaton doctor           # health check: your AI provider and all local tools
```

## Quick start

Clone this repository from GitHub. Optionally set up a virtual environment
first, then from the project folder run:

```bash
pip install .
keaton doctor
```

Then just describe what you need:

```bash
keaton run "compress this video"
keaton run "find every TODO in this repo"
keaton run "convert notes.md to a pdf"
keaton run "show my running containers"
keaton run "back up my postgres database"
```

Keaton picks the tool, shows you the command, and (for anything risky) asks
before it pulls the trigger.

## How it is built

```
keaton/
  tools/
    base.py        # the Tool interface every tool inherits
    registry.py    # discovery and natural language routing
    executor.py    # validation, confirmation, timing, streaming
    git.py  ffmpeg.py  docker.py  kubectl.py  terraform.py
    python.py  node.py  package_manager.py  imagemagick.py
    pandoc.py  ytdlp.py  ripgrep.py  fd.py  jq.py  ssh.py
    sqlite.py  postgres.py  mysql.py
  toolcli.py       # the tools, tool, and run commands
  splash.py        # animated pixel art startup splash
  assets/          # the bundled pixel art portrait
  cli.py           # entry point
  providers/       # pluggable AI backends
```

On launch, Keaton fades in a little pixel art portrait. Replay it any time with
`keaton splash`, or turn it off with `keaton config` (`splash_enabled`) or by
setting `KEATON_NO_SPLASH=1`. Regenerate it from any photo with
`python scripts/gen_pixel_art.py path/to/photo.jpg`.

Every tool is a small, declarative subclass of `Tool`. It says what it is
called, what binary it wraps, which words should route to it, what it can do,
and a few example commands. The registry finds it automatically, which is
exactly why new tools are cheap to add.

## Adding your own tool

```python
# keaton/tools/mytool.py
from .base import Tool

class MyTool(Tool):
    name = "mytool"
    binary = "mytool"
    category = "misc"
    description = "Does the thing."
    keywords = ["thing", "do the thing"]
    capabilities = ["Thing A", "Thing B"]
    examples = [("do the thing to foo", "mytool foo")]
    recipes = {"do": ["{target}"]}
```

Save it. Run `keaton tools`. It is there.

## Safety, briefly

Keaton is deliberately conservative. It never hides a command from you, it
confirms anything destructive, it supports dry runs, and for tools that can
validate (like Terraform) it leans on their own validation first. It only uses
the media downloader in ways that respect each platform's terms of service.

## License

MIT. See the LICENSE file.
