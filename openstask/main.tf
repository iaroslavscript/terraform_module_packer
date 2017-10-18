provider "openstackpatched" {
  insecure = true
}

data "openstackpatched_images_image_v2" "image_request" {
  name           = "${var.image_name}"
  most_recent    = "${var.most_recent}"
  error_on_empty = false
}

data "external" "packer_build" {
  program = ["python", "${path.module}/packer-wrapper.py"]
  query = "${merge(map("template_file", var.packer_build_template, "rebuild", format("%v", var.packer_rebuild), "timeout", format("%v", var.packer_build_timeout)), var.packer_build_template_vars, map("image_id", data.openstackpatched_images_image_v2.image_request.id, "image_name", var.image_name))}"
}

resource "null_resource" "echo_packer_build" {
  provisioner "local-exec" {
    command = "/bin/echo ${data.external.packer_build.result.log}"
  }
}

