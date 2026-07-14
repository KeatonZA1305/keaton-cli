from .base import Tool


class TerraformTool(Tool):
    name = "terraform"
    binary = "terraform"
    category = "infra"
    description = "Infrastructure as code: validate, plan, apply, destroy."
    install_hint = "Install: https://developer.hashicorp.com/terraform/install"
    keywords = ["terraform", "infrastructure", "plan", "apply", "destroy",
                "validate", "iac", "provision", "module"]
    capabilities = [
        "init / validate / plan", "apply (guarded)", "destroy (guarded)",
        "Module scaffolding", "Best-practice hints",
    ]
    examples = [
        ("validate my terraform", "terraform validate"),
        ("show me the plan", "terraform plan"),
        ("apply the changes", "terraform apply"),
    ]
    recipes = {
        "init": ["init"],
        "validate": ["validate"],
        "plan": ["plan"],
        "apply": ["apply"],
        "destroy": ["destroy"],
    }
    destructive = {"apply", "destroy"}
