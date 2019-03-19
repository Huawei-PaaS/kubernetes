#!/bin/bash

#
# USAGE:
# patch_resources.sh [deployment name] [container name] [memory limit] [memory request] 
#

set -x

dep=$1
containerName=$2
mem1=$3
mem2=$4

/root/pengdu/code/github-k8s/_output/bin/kubectl -s="http://10.122.48.55:8888" patch deployment $dep --patch \
							'{"spec":{"template":{"spec":{"containers":[{"name":"'$containerName'", "resources":{"limits":{"memory":"'$mem1'Gi"},"requests":{"memory":"'$mem2'Gi"}}}]}}}}'
