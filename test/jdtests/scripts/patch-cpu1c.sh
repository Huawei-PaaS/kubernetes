#!/bin/bash

set -x

dep=$1
container=$2
var1=$3
var2=$4

/root/pengdu/code/github-k8s/_output/bin/kubectl -s="http://10.122.48.55:8888" patch deployment $dep --patch \
							'{"spec":{"template":{"spec":{"containers":[{"name":"'$container'", "resources":{"limits":{"cpu":"'$var1'"},"requests":{"cpu":"'$var2'"}}}]}}}}'
