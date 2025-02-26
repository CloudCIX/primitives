#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import cpu_hyperv

# Run the following test scripts before this one:
# * `tools/test_ns.py build mynetns` to ensure the name space exists
# * `tools/test_vlanif_ns.py build {vlan} to ensure vlan tagged interface exists on podnet
# * `tools/test_network_ns.py build mynetns` to ensure the name space exists
# * `tools/test_hyperv.py build 2a02:2078:9::20:0:1 robot.devtest-cork-01.cloudcix.net 1234_5678` to ensure there is a VM to operate on
# * `tools/test_hyperv.py quiesce 2a02:2078:9::20:0:1 None 1234_5678` to ensure the VM is in the correct state for modifying CPU count.

cmd = sys.argv[1]

host = None
ram = 4

if len(sys.argv) > 2:
    host = sys.argv[2]

if len(sys.argv) > 3:
    vm_identifier = sys.argv[3]

if len(sys.argv) > 4:
    cpu = sys.argv[4]

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

if vm_identifier is None:
    print('vm_identifier is required, please the vm_identifier as third argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'update':
    status, msg = cpu_hyperv.update(
        host=host,
        vm_identifier=vm_identifier,
        cpu=cpu,
    )
elif cmd == 'read':
    status, data, msg = cpu_hyperv.read(host=host, vm_identifier=vm_identifier)
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
