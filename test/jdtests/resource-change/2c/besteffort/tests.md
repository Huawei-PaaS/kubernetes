Any patch command should fail due to Qos changes, such as

```
patch-memory2c.sh e2e-test sd1 8 8 sd2 9 8 
patch-cpu2c.sh e2e-test sd1 6 5 sd2 4 4 
```

