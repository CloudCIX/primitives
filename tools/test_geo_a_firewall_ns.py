#!/usr/bin/env python3

import sys
import json
from cloudcix_primitives import geo_a_firewall_ns

# Prerequisites for running this test script:
#
#   tools/test_ns.py build ns1100
#   tools/test_bridgeif_ns.py build br-B1 ns1100
#   tools/test_default_firewall_ns.py build ns1100 br-B1
#   tools/test_set_firewall_ns.py build ns1100 IE_V4 ipv4_addr
#   tools/test_set_firewall_ns.py update ns1100 IE_V4 '8.8.8.8, 1.1.1.1, 192.168.0.1/24'
#   tools/test_set_firewall_ns.py build ns1100 GB_V4 ipv4_addr
#   tools/test_set_firewall_ns.py update ns1100 GB_V4 '9.9.9.9, 2.2.2.2, 192.168.0.1/24'
#   tools/test_set_firewall_ns.py build ns1100 IS_V6 ipv6_addr
#   tools/test_set_firewall_ns.py update ns1100 IS_V6 '2600:1406:3a00:21::173e:2e65, 2600:1406:3a00:21::173e:2e66, 5:6:7::/64'

# Fetch command and arguments
cmd = sys.argv[1] if len(sys.argv) > 1 else None
namespace_name = "ns1100"
inbound=[
    'IE_V4', 
    'GB_V4',
    'IS_V6',
]

outbound=[
    'IE_V4', 
    'GB_V4',
    'IS_V6',
]

config_file = "/etc/cloudcix/pod/configs/config.json"

if len(sys.argv) > 2:
    namespace_name = sys.argv[2]
if len(sys.argv) > 3:
    inbound = json.loads(sys.argv[3])
if len(sys.argv) > 3:
    outbound = json.loads(sys.argv[4])


status = None
msg = None
data = None

# Check and execute command
if cmd == 'build':
    status, msg = geo_a_firewall_ns.build(namespace_name, inbound, outbound, config_file)
elif cmd == 'read':
    status, data, msg = geo_a_firewall_ns.read(namespace_name, config_file)
elif cmd == 'scrub':
    status, msg = geo_a_firewall_ns.scrub(namespace_name, config_file)
else:
   print(f"Unknown command: {cmd}")
   sys.exit(1)


# Output the status and messages
print("Status: %s" % status)
print("\nMessage:")
if isinstance(msg, list):
    for item in msg:
        print(item)
else:
    print(msg)

# Output data if available
if data is not None:
    print("\nData:")
    print(json.dumps(data, sort_keys=True, indent=4))
