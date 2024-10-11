#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import dhcpns

# Run the following test scripts before this one:
#
# * `tools/test_directorymain_primitive.py build /etc/netns/mynetns` to ensure the directories needed
#   are in place.
# * `tools/test_ns_primitive.py build mynetns to ensure the name space we want to run dhcpns in exists

cmd = sys.argv[1]

namespace = 'mynetns'

dhcp_ranges =[
{
    'ip_start': '192.168.55.10',
    'ip_end': '192.168.55.254',
    'mask': '255.255.255.0',
},
{
    'ip_start': '192.168.62.2',
    'ip_end': '192.168.62.254',
    'mask': '255.255.255.0',
}]

dhcp_hosts =[
{
    'ip_address': '192.168.55.12',
    'mac_address': '4e:f2:b8:02:57:50',
},
{
    'ip_address': '192.168.62.8',
    'mac_address': '4e:f2:b8:02:57:5a',
}]



if len(sys.argv) > 2:
    namespace = sys.argv[2]


status = None
msg = None
data = None

if cmd == 'build':
    status, msg = dhcpns.build(namespace, dhcp_ranges, dhcp_hosts, "/etc/cloudcix/pod/configs/config.json")
if cmd == 'scrub':
    status, msg = dhcpns.scrub(namespace, "/etc/cloudcix/pod/configs/config.json")
if cmd == 'read':
    status, data, msg = dhcpns.read(namespace, "/etc/cloudcix/pod/configs/config.json")

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