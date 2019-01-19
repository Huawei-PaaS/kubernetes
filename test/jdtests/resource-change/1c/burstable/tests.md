## Memory tests

First, increase memory

```
patch-memory1c.sh e2e-test sd1 5 4
```

Then, decrease memory
```
patch-memory1c.sh e2e-test sd1 3 2
```

## Cpu tests

First, increase cpu 
```
patch-cpu1c.sh e2e-test sd1 9 8 
```

Then, decrease cpu 
```
patch-cpu1c.sh e2e-test sd1 7 6
```

## Qos tests (attempting to change QOS, should fail)
```
patch-memory1c.sh e2e-test sd1 5 5  
patch-cpu1c.sh e2e-test sd1 5 5  
```

Note: *Only* the 2nd of this two patch commands should fail because the it will trigger the QOS change. 

## Verification

On the pod machine

```
cid=`docker ps|grep k8s_sd|awk '{print $1}'`
docker inspect $cid | grep "\"CpuQuota\""
docker inspect $cid | grep "\"Memory\"" 
```
