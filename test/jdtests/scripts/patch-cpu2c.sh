#!/bin/bash

set -x

dep=$1
container1=$2
var1=$3
var2=$4
container2=$5
var3=$6
var4=$7

/root/pengdu/code/github-k8s/_output/bin/kubectl -s="http://10.122.48.55:8888" patch deployment $dep --patch \
							'{"spec":{"template":{"spec":{"containers":[{"name":"'$container1'", "resources":{"limits":{"cpu":"'$var1'"},"requests":{"cpu":"'$var2'"}}}, {"name":"'$container2'", "resources":{"limits":{"cpu":"'$var3'"},"requests":{"cpu":"'$var4'"}}}]}}}}'
