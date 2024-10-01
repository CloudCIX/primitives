#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import bridgeifns

cmd = sys.argv[1]

bridgename, namespace_name = "testbridge", "testns"

if len(sys.argv) > 2:
    bridgename = sys.argv[2]
    namespace_name = sys.argv[2]


status = None
msg = None
data = None

if cmd == 'build':
    status, msg = bridgeifns.build(bridgename, namespace_name, "169.254.169.254", "/etc/cloudcix/pod/configs/config.json")
if cmd == 'scrub':
    status, msg = bridgeifns.scrub(bridgename, namespace_name, "/etc/cloudcix/pod/configs/config.json")
if cmd == 'read':
    status, data, msg = bridgeifns.read(bridgename, namespace_name, "169.254.169.254", "/etc/cloudcix/pod/configs/config.json")

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
