Any patch command should fail due to Qos changes, such as

```
patch-memory1c.sh e2e-test sd1 5 5  
patch-memory1c.sh e2e-test sd1 6 5  
patch-cpu1c.sh e2e-test sd1 7 7
patch-cpu1c.sh e2e-test sd1 8 5  
```

