#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import snapshot_hyperv

# Run the following test scripts before this one:
#
# *  `tools/test_directory_hyperv.py build "D:\\HyperV\\myvm"`
#
# *  `tools/test_hyperv.py build "<host_ip>" "D:\\HyperV\\primitive_test" `
#

cmd = sys.argv[1]

host = None
domain = 'primitive_test'
snapshot = 'snapshot_123'
remove_subtree = False

if len(sys.argv) > 2:
    host = sys.argv[2]

if len(sys.argv) > 3:
    domain = sys.argv[3]

if len(sys.argv) > 4:
    snapshot = sys.argv[4]

if len(sys.argv) > 5:
    remove_subtree = sys.argv[5]

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = snapshot_hyperv.build(host=host, domain=domain, snapshot=snapshot)
elif cmd == 'read':
    status, data, msg = snapshot_hyperv.read(host=host, domain=domain, snapshot=snapshot)
elif cmd == 'scrub':
    status, msg = snapshot_hyperv.scrub(host=host, domain=domain, snapshot=snapshot, remove_subtree=remove_subtree)
elif cmd == 'update':
    status, msg = snapshot_hyperv.update(host=host, domain=domain, snapshot=snapshot)
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
