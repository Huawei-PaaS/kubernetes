Patch the resource:

```
patch-memory1c.sh e2e-test sd1 4 4
```

Because of the following policy setting:

```
scheduler.alpha.kubernetes.io/resize-resources-policy: "Restart"
```

Pod will be restarted with the updated resource 4G memory request and limit. Verified by

```
cid=`docker ps|grep k8s_sd|awk '{print $1}'`
docker inspect $cid | grep "\"Memory\""
```

on the pod node.
