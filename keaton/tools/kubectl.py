from .base import Tool


class KubectlTool(Tool):
    name = "kubectl"
    binary = "kubectl"
    category = "containers"
    description = "Drive Kubernetes clusters: pods, services, deployments, logs."
    install_hint = "Install: https://kubernetes.io/docs/tasks/tools/"
    keywords = ["kubectl", "kubernetes", "k8s", "pod", "namespace", "deployment",
                "service", "configmap", "secret", "port-forward", "cluster", "helm"]
    capabilities = [
        "Pods / services / deployments", "Namespaces", "Logs", "Port forwarding",
        "ConfigMaps & secrets", "Apply manifests", "Cluster diagnostics",
    ]
    examples = [
        ("list my pods", "kubectl get pods"),
        ("apply this manifest", "kubectl apply -f deploy.yaml"),
        ("show logs for a pod", "kubectl logs <pod>"),
        ("what namespaces exist", "kubectl get ns"),
    ]
    recipes = {
        "pods": ["get", "pods"],
        "services": ["get", "svc"],
        "apply": ["apply", "-f", "{file}"],
        "logs": ["logs", "{pod}"],
    }
    destructive = {"delete"}
