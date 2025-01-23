#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import nginx_ns

# Run the following test scripts before this one:
# 
# * `tools/test_ns.py build mynetns to ensure the name space we want to run exists
# * `tools/test_cidata.py build /etc/netns/mynetns/cloudcix-metadata/10.0.0.3/v1` to give the web server something to serve

cmd = sys.argv[1]
config_file = "/etc/cloudcix/pod/configs/config.json"
namespace = 'mynetns'

if len(sys.argv) > 2:
    namespace = sys.argv[2]

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = nginx_ns.build(namespace, config_file)
elif cmd == 'read':
    status, data, msg = nginx_ns.read(namespace, config_file)
elif cmd == 'scrub':
    status, msg = nginx_ns.scrub(namespace, config_file)
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
