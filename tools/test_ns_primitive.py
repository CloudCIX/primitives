#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import ns

cmd = sys.argv[1]

namespace_name = "testns"

if len(sys.argv) > 2:
    namespace_name = sys.argv[2]

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = ns.build(namespace_name, "169.254.169.254", "/etc/cloudcix/pod/configs/config.json")
if cmd == 'scrub':
    status, msg = ns.scrub(namespace_name, "/etc/cloudcix/pod/configs/config.json")
if cmd == 'read':
    status, data, msg = ns.read(namespace_name, "169.254.169.254", "/etc/cloudcix/pod/configs/config.json")

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
