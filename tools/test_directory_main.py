#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import directory_main

cmd = sys.argv[1]
config_file = "/etc/cloudcix/pod/configs/config.json"

dir_name = "/etc/netns/mynetns/"

if len(sys.argv) > 2:
    dir_name = sys.argv[2]

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = directory_main.build(dir_name, config_file)
elif cmd == 'read':
    status, data, msg = directory_main.read(dir_name, config_file)
elif cmd == 'scrub':
    status, msg = directory_main.scrub(dir_name, config_file)
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
