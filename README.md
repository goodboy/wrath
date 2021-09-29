# wrath

A TCP SYN port scanner, designed to scan 64K ports as quickly as possible.

Currently work in progress.

The main strategy is splitting 64K port range into smaller batches (configurable with `-b`), and uniformly distribute the load among CPU cores.
It spawns as many actors as there are cores, and assigns each actor to run a batchworker. Everything that happens in the batchworker is asynchronous.
Thus, the joint force of two great libs (trio and tractor) unleashes the full power of asynchrony united with parallelism.

# Small thing before you start scanning

For experimenting, I have changed the maximum open files limit imposed by the OS. I've set it to 2^17. The current version works under this assumption,
I haven't tested it (yet) under normal circumstances.  

# HowTo

```shell
$ time sudo env/bin/python -m wrath 192.168.1.1 -p 0-65535 -b 16384
port 53: open
port 80: open
port 18017: open
port 3394: open
port 3838: open
port 5473: open
port 9100: open
port 45304: open
port 515: open

real	0m10,912s
user	0m19,984s
sys	0m2,791s
```