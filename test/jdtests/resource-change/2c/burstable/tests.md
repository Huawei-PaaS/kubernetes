## Memory tests

First, increase memory

```
patch-memory2c.sh e2e-test sd1 9 8 sd2 7 6
```

Then, decrease memory

```
patch-memory2c.sh e2e-test sd1 3 2 sd2 5 4
```

Then increase one and decrease the other 

```
patch-memory2c.sh e2e-test sd1 9 8 sd2 2 1
```

## Cpu tests

First, increase cpu

```
patch-cpu2c.sh e2e-test sd1 9 8 sd2 7 6
```

Then, decrease cpu

```
patch-cpu2c.sh e2e-test sd1 3 2 sd2 5 4
```

Then increase one and decrease the other 

```
patch-cpu2c.sh e2e-test sd1 9 8 sd2 2 1
```

## Qos tests (attempting to change QOS, should fail)

```
patch-memory2c.sh e2e-test sd1 8 8 sd2 9 9 
patch-cpu2c.sh e2e-test sd1 5 5 sd2 4 4 
```

Note: *Only* the 2nd of this two patch commands should fail because the it will trigger the QOS change. 

## Verification

On the pod machine

```
cid1=`docker ps|grep k8s_sd1|awk '{print $1}'`;docker inspect $cid1 | grep "\"Memory\"";docker inspect $cid1 | grep "\"CpuQuota\""
cid2=`docker ps|grep k8s_sd2|awk '{print $1}'`;docker inspect $cid2 | grep "\"Memory\"";docker inspect $cid2 | grep "\"CpuQuota\""
```
