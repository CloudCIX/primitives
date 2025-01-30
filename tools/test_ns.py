#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import ns

cmd = sys.argv[1]
config_file = "/etc/cloudcix/pod/configs/config.json"
namespace_name = "mynetns"

if len(sys.argv) > 2:
    namespace_name = sys.argv[2]

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = ns.build(namespace_name, "169.254.169.254", config_file)
elif cmd == 'read':
    status, data, msg = ns.read(namespace_name, "169.254.169.254", config_file)
elif cmd == 'scrub':
    status, msg = ns.scrub(namespace_name, config_file)
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
