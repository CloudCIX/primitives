#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import vlanif_ns

# Run the following test scripts before this one:
#
# * `tools/test_ns.py build mynetns to ensure the name space we want exists

cmd = sys.argv[1]
config_file = "/etc/cloudcix/pod/configs/config.json"
namespace = 'mynetns'

vlan = 4000
ifname = 'private0'


if len(sys.argv) > 2:
    namespace = sys.argv[2]
if len(sys.argv) > 3:
    vlan = sys.argv[3]
if len(sys.argv) > 4:
    ifname = sys.argv[4]


status = None
msg = None
data = None

if cmd == 'build':
    status, msg = vlanif_ns.build(vlan, ifname, namespace, config_file)
elif cmd == 'scrub':
    status, msg = vlanif_ns.scrub(vlan, ifname, namespace, config_file)
elif cmd == 'read':
    status, data, msg = vlanif_ns.read(vlan, ifname, namespace, config_file)
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