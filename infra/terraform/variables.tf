variable "aws_region" {
  description = "AWS region in which to create the EKS cluster."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Name for the EKS cluster and its VPC."
  type        = string
  default     = "opspilot"
}

variable "cluster_version" {
  description = "Kubernetes version currently supported by EKS in the selected region."
  type        = string
}

variable "allowed_cidr_blocks" {
  description = "Trusted client CIDR blocks allowed to reach the public EKS API endpoint."
  type        = list(string)

  validation {
    condition = length(var.allowed_cidr_blocks) > 0 && alltrue([
      for cidr in var.allowed_cidr_blocks :
      can(cidrnetmask(cidr)) && cidr != "0.0.0.0/0"
    ])
    error_message = "Provide valid IPv4 CIDRs and do not allow 0.0.0.0/0."
  }
}

variable "node_instance_type" {
  description = "EC2 instance type used by the EKS managed node group."
  type        = string
  default     = "t3.medium"
}
