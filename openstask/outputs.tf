output "log" {
  value = "${data.external.packer_build.result.log}"
}

output "image_id" {
  value = "${data.external.packer_build.result.image_id}"
}

output "image_name" {
  value = "${var.image_name}"
}
