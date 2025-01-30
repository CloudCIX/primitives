#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import dhcp_ns

# Run the following test scripts before this one:
#
# * `tools/test_directory_main.py build /etc/netns/mynetns` to ensure the directories needed
#   are in place.
# * `tools/test_ns.py build mynetns to ensure the name space we want to run dhcpns in exists

cmd = sys.argv[1]
config_file = "/etc/cloudcix/pod/configs/config.json"

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
    status, msg = dhcp_ns.build(namespace, dhcp_ranges, dhcp_hosts, config_file)
elif cmd == 'read':
    status, data, msg = dhcp_ns.read(namespace, config_file)
elif cmd == 'scrub':
    status, msg = dhcp_ns.scrub(namespace, config_file)
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