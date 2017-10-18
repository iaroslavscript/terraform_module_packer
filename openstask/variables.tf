variable "image_name" {}

variable "most_recent" {
  default = true
}

variable "packer_build_template" {}

variable "packer_build_template_vars" {
  type    = "map"
  default = {}
}

variable "packer_build_timeout" {
  default = 600
}

variable "packer_rebuild" {
  default = false
}

