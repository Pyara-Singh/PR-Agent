variable "namespace" {
  type    = string
  default = "proofmerge"
}

variable "helm_values_file" {
  type        = string
  description = "Path to a private Helm values file containing managed service endpoints and secrets."
}

resource "kubernetes_namespace" "proofmerge" {
  metadata {
    name = var.namespace
  }
}

resource "helm_release" "proofmerge" {
  name       = "proofmerge"
  namespace  = kubernetes_namespace.proofmerge.metadata[0].name
  chart      = "../helm/proofmerge"
  values     = [file(var.helm_values_file)]
  atomic     = true
  timeout    = 600
  depends_on = [kubernetes_namespace.proofmerge]
}

