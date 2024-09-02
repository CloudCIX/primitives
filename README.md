# Primitives

## net_main
Primtive for Building Interface System Service on PodNet.

Supported verbs:

- build
  - host: str
  - ifname: str
  - config_filepath: optional str
  - ips: optional list of str
  - mac: optional str
  - routes: optional list of str
  - vlan: optional int

- quiesce
  - host: str
  - ifname: str
  - config_filepath: optional str 
  - vlan: optional int
 
- restart 
  - host: str
  - ifname: str
  - config_filepath: optional str 
  - vlan: optional int
 