First, increase the memory request within the node's limit, for example: 

```
patch-memory1c.sh e2e-test sd1 4 4
```

Because of the following policy setting:

```
scheduler.alpha.kubernetes.io/resize-resources-policy: "InPlacePreferred"
```

Pod will be updated without restart. 

Verify resource has been updated correctly

```
cid=`docker ps|grep k8s_sd|awk '{print $1}'`
docker inspect $cid | grep "\"Memory\""
```

on the pod node.

Then increase the memory request over the node's limit, for example:

```
patch-memory1c.sh e2e-test sd1 10000 10000
```

This will cause the pod to be recreated with the updated resource (1000 in this example). If there's no host in the cluster that can satisfy the memory request, the new  pod will go into pending as a result.
