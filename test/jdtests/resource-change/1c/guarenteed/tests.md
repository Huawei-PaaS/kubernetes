## Memory tests

First, increase memory
```
patch-memory1c.sh e2e-test sd1 4 4
```

Then, decrease memory
```
patch-memory1c.sh e2e-test sd1 3 3 
```

## Cpu tests

First, increase cpu 
```
patch-cpu1c.sh e2e-test sd1 8 8 
```

Then, decrease cpu 
```
patch-cpu1c.sh e2e-test sd1 7 7 
```

## Qos tests (attempting to change QOS, should fail)
```
patch-memory1c.sh e2e-test sd1 6 5  
patch-cpu1c.sh e2e-test sd1 6 5  
```

Note: *Both* of these two patch commands should fail 

## Verification

On the pod machine

```
cid=`docker ps|grep k8s_sd|awk '{print $1}'`
docker inspect $cid | grep "\"CpuQuota\""
docker inspect $cid | grep "\"Memory\"" 
```
