#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import bridgemain


cmd = sys.argv[1]

address_range = None
bridge = 'BM1'

if len(sys.argv) > 2:
    address_range = sys.argv[2]

if len(sys.argv) > 3:
    bridge = sys.argv[3]


status = None
msg = None
data = None

if cmd == 'build':
    status, msg = bridgemain.build(bridge=bridge, address_range=address_range)
if cmd == 'scrub':
    status, msg = bridgemain.scrub(bridge=bridge)
if cmd == 'read':
    status, data, msg = bridgemain.read(bridge=bridge)

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
