#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import storage_hyperv

cmd = sys.argv[1]

host = None
domain_path = 'D:\HyperV\primitive_test\\'
storage = 'primitive_test.vhdx'
size = 5

if len(sys.argv) > 2:
    host = sys.argv[2]

if len(sys.argv) > 3:
    domain_path = sys.argv[3]

if len(sys.argv) > 4:
    storage = sys.argv[4]

if len(sys.argv) > 5:
    size = sys.argv[5]

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = storage_hyperv.build(
        host=host, domain_path=domain_path, storage=storage, size=size
    )
if cmd == 'update':
    status, msg = storage_hyperv.update(
        host=host, domain_path=domain_path, storage=storage, size=size
    )
if cmd == 'scrub':
    status, msg = storage_hyperv.scrub(host=host, domain_path=domain_path, storage=storage)
if cmd == 'read':
    status, data, msg = storage_hyperv.read(host=host, domain_path=domain_path, storage=storage)

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
