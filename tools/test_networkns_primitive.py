#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import networkns

# Run the following test scripts before this one:
#
# * `tools/test_directorymain_primitive.py build /etc/netns/mynetns` to ensure the directories needed
#   are in place.
# * `tools/test_ns_primitive.py build mynetns to ensure the name space we want to run dhcpns in exists

cmd = sys.argv[1]

namespace = 'mynetns'

address_range = '10.0.0.1/24'
device = 'private0.4000'


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
    status, msg = networkns.build(address_range, device, namespace, "/etc/cloudcix/pod/configs/config.json")
if cmd == 'scrub':
    status, msg = networkns.scrub(address_range, device, namespace, "/etc/cloudcix/pod/configs/config.json")
if cmd == 'read':
    status, data, msg = networkns.read(address_range, device, namespace, "/etc/cloudcix/pod/configs/config.json")

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