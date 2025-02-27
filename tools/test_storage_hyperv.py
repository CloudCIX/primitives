#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import storage_hyperv

cmd = sys.argv[1]

host = None
vm_identifier = '1234_5678'
storage_identifier = None
size = 5

if len(sys.argv) > 2:
    host = sys.argv[2]

if len(sys.argv) > 3:
    vm_identifier = sys.argv[3]

if len(sys.argv) > 4:
    storage_identifier = sys.argv[4]
else:
    storage_identifier = vm_identifier + "-secondary"

if len(sys.argv) > 5:
    size = int(sys.argv[5])

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg, successful_payloads = storage_hyperv.build(host=host, vm_identifier=vm_identifier, storage_identifier=storage_identifier, size=size)
elif cmd == 'read':
    status, data, msg = storage_hyperv.read(host=host, vm_identifier=vm_identifier, storage_identifier=storage_identifier)
elif cmd == 'scrub':
    status, msg, successful_payloads = storage_hyperv.scrub(host=host, vm_identifier=vm_identifier, storage_identifier=storage_identifier)
elif cmd == 'update':
    status, msg, successful_payloads = storage_hyperv.update(host=host, vm_identifier=vm_identifier, storage_identifier=storage_identifier, size=size)
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
