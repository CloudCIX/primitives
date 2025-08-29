#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import vlanif_lxd

# Run the following test scripts before this one:
#
# * `tools/test_ns.py build mynetns to ensure the name space we want to run dhcpns in exists
# * `tools/test_vlanif_ns.py build {vlan} to ensure vlan tagged interface exists on podnet
# * `tools/test_bridge_lxd.py build br1002 to ensure the LXD bridge exists to connect to the vlan tagged interface

cmd = sys.argv[1]

host=None
vlan=1002
ifname='cloud0'

if len(sys.argv) > 2:
    host = sys.argv[2]
if len(sys.argv) > 3:
    vlan = sys.argv[3]
if len(sys.argv) > 4:
    ifname = sys.argv[4]

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = vlanif_lxd.build(host=host, vlan=vlan, ifname=ifname)
elif cmd == 'read':
    status, data, msg = vlanif_lxd.read(host=host, vlan=vlan)
elif cmd == 'scrub':
    status, msg = vlanif_lxd.scrub(host=host, vlan=vlan)
else:
   print(f"Unknown command: {cmd}")
   sys.exit(1)


print("Status: %s" %  status)
print()
print("Message:")
if type(msg) == list:
    for item in msg:
        print(item)
else:
    print(msg)

if data is not None:
    print()
    print("Data:")
    print(json.dumps(data, sort_keys=True, indent=4))
