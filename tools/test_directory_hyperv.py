#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import directory_hyperv

cmd = sys.argv[1]

host = None
path = 'D:\HyperV\directory_test\\'

if len(sys.argv) > 2:
    host = sys.argv[2]

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = directory_hyperv.build(host, path)
if cmd == 'scrub':
    status, msg = directory_hyperv.scrub(host, path)
if cmd == 'read':
    status, data, msg = directory_hyperv.read(host, path)

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
