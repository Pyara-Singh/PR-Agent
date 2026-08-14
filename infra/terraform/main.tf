variable "namespace" {
  type    = string
  default = "pr-agent"
}

variable "helm_values_file" {
  type        = string
  description = "Path to a private Helm values file containing managed service endpoints and secrets."
}

resource "kubernetes_namespace" "pr_agent" {
  metadata {
    name = var.namespace
  }
}

resource "helm_release" "pr_agent" {
  name       = "pr-agent"
  namespace  = kubernetes_namespace.pr_agent.metadata[0].name
  chart      = "../helm/PR_Agent"
  values     = [file(var.helm_values_file)]
  atomic     = true
  timeout    = 600
  depends_on = [kubernetes_namespace.pr_agent]
}

