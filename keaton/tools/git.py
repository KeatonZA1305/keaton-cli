from .base import Tool


class GitTool(Tool):
    name = "git"
    binary = "git"
    category = "vcs"
    description = "Version control: status, commits, branches, history, PRs."
    install_hint = "Install: https://git-scm.com/downloads"
    keywords = ["git", "commit", "branch", "merge", "rebase", "stash",
                "diff", "repository", "repo", "tag", "cherry-pick", "checkout"]
    capabilities = [
        "Status & diff", "Commit (with generated messages)", "Branch create/switch",
        "Merge / rebase / cherry-pick", "Tag & stash management",
        "History & repository summary", "Conflict assistance", "PR description drafting",
    ]
    examples = [
        ("show me the repo status", "git status -sb"),
        ("what changed", "git diff"),
        ("commit everything with a message", "git commit -am 'your message'"),
        ("make a branch called feature-x", "git switch -c feature-x"),
        ("show the last 10 commits", "git log --oneline -10"),
    ]
    recipes = {
        "status": ["status", "-sb"],
        "diff": ["diff"],
        "log": ["log", "--oneline", "-{n}"],
        "branch": ["switch", "-c", "{name}"],
        "stash": ["stash"],
    }
    destructive = {"reset-hard", "clean"}
