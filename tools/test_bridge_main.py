#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import bridge_main


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
    status, msg = bridge_main.build(bridge=bridge, address_range=address_range)
elif cmd == 'read':
    status, data, msg = bridge_main.read(bridge=bridge)
elif cmd == 'scrub':
    status, msg = bridge_main.scrub(bridge=bridge)
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
