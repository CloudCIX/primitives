#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import network_ns

# Run the following test scripts before this one:
#
# * `tools/test_ns.py build mynetns to ensure the name space we want exists

cmd = sys.argv[1]

namespace = 'mynetns'

address_range = '10.0.0.1/24'
device = 'private0.4000' 
config_file = "/etc/cloudcix/pod/configs/config.json"

if len(sys.argv) > 2:
    namespace = sys.argv[2]
if len(sys.argv) > 3:
    address_range = sys.argv[3]
if len(sys.argv) > 4:
    device = sys.argv[4]


status = None
msg = None
data = None

if cmd == 'build':
    status, msg = network_ns.build(address_range, device, namespace, config_file)
elif cmd == 'read':
    status, data, msg = network_ns.read(address_range, device, namespace, config_file)
elif cmd == 'scrub':
    status, msg = network_ns.scrub(address_range, device, namespace, config_file)
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