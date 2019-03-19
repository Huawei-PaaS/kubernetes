## Memory tests

First, increase memory

```
patch-memory2c.sh e2e-test sd1 8 8 sd2 9 9
```

Then, decrease memory

```
patch-memory2c.sh e2e-test sd1 2 2 sd2 4 4
```

Then increase one and decrease the other 

```
patch-memory2c.sh e2e-test sd1 3 3 sd2 1 1
```

## Cpu tests

First, increase cpu

```
patch-cpu2c.sh e2e-test sd1 8 8 sd2 9 9
```

Then, decrease cpu

```
patch-cpu2c.sh e2e-test sd1 2 2 sd2 4 4
```

Then increase one and decrease the other 

```
patch-cpu2c.sh e2e-test sd1 3 3 sd2 1 1
```

## Qos tests (attempting to change QOS, should fail)
```
patch-memory2c.sh e2e-test sd1 8 8 sd2 9 8 
patch-cpu2c.sh e2e-test sd1 6 5 sd2 4 4 
```

Note: *Both* of these two patch commands should fail 

## Verification

On the pod machine

```
cid1=`docker ps|grep k8s_sd1|awk '{print $1}'`;docker inspect $cid1 | grep "\"Memory\"";docker inspect $cid1 | grep "\"CpuQuota\""
cid2=`docker ps|grep k8s_sd2|awk '{print $1}'`;docker inspect $cid2 | grep "\"Memory\"";docker inspect $cid2 | grep "\"CpuQuota\""
```

