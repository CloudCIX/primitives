#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import bridge_kvm

# Run the following test scripts before this one:
#
# * `tools/test_directorymain_primitive.py build /etc/netns/mynetns` to ensure the directories needed
#   are in place.
# * `tools/test_ns_primitive.py build mynetns to ensure the name space we want to run dhcpns in exists

cmd = sys.argv[1]

host=None
vlan=4000
ifname='cloud0'

if len(sys.argv) > 2:
    host = sys.argv[2]
if len(sys.argv) > 3:
    vlan = sys.argv[3]
if len(sys.argv) > 4:
    ifname = sys.argv[4]

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = bridge_kvm.build(host=host, vlan=vlan, ifname=ifname)
if cmd == 'scrub':
    status, msg = bridge_kvm.scrub(host=host, vlan=vlan)
if cmd == 'read':
    status, data, msg = bridge_kvm.read(host=host, vlan=vlan)

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
