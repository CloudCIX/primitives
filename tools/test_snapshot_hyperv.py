#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import snapshot_hyperv

# Run the following test scripts before this one:
# * `tools/test_ns.py build mynetns` to ensure the name space exists
# * `tools/test_vlanif_ns.py build {vlan} to ensure vlan tagged interface exists on podnet
# * `tools/test_network_ns.py build mynetns` to ensure the name space exists
# * `tools/test_hyperv.py build <host> <region_url> build 1234_5678 

cmd = sys.argv[1]

host = None
vm_identifier = '1234_5678'
snapshot_identifier = 'snapshot_123'
remove_subtree = False

if len(sys.argv) > 2:
    host = sys.argv[2]

if len(sys.argv) > 3:
    vm_identifier = sys.argv[3]

if len(sys.argv) > 4:
    snapshot_identifier = sys.argv[4]

if len(sys.argv) > 5:
    remove_subtree = bool(sys.argv[5])

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = snapshot_hyperv.build(host=host, vm_identifier=vm_identifier, snapshot_identifier=snapshot_identifier)
elif cmd == 'read':
    status, data, msg = snapshot_hyperv.read(host=host, vm_identifier=vm_identifier, snapshot_identifier=snapshot_identifier)
elif cmd == 'list':
    status, data, msg = snapshot_hyperv.list(host=host, vm_identifier=vm_identifier)
elif cmd == 'scrub':
    status, msg = snapshot_hyperv.scrub(host=host, vm_identifier=vm_identifier, snapshot_identifier=snapshot_identifier, remove_subtree=remove_subtree)
elif cmd == 'update':
    status, msg = snapshot_hyperv.update(host=host, vm_identifier=vm_identifier, snapshot_identifier=snapshot_identifier)
else:
   print(f"Unknown command: {cmd}")
   sys.exit(1)


print("Status: %s" % status)
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
