#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import vlanifns

# Run the following test scripts before this one:
#
# * `tools/test_directorymain_primitive.py build /etc/netns/mynetns` to ensure the directories needed
#   are in place.
# * `tools/test_ns_primitive.py build mynetns to ensure the name space we want to run dhcpns in exists

cmd = sys.argv[1]

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
    status, msg = vlanifns.build(vlan, ifname, namespace, "/etc/cloudcix/pod/configs/config.json")
if cmd == 'scrub':
    status, msg = vlanifns.scrub(vlan, ifname, namespace, "/etc/cloudcix/pod/configs/config.json")
if cmd == 'read':
    status, data, msg = vlanifns.read(vlan, ifname, namespace, "/etc/cloudcix/pod/configs/config.json")


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