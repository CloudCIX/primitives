#!/usr/bin/env python3

import sys
import json
from cloudcix_primitives import project_firewall_ns

# Prerequisites for running this test script:
#
#   tools/test_ns.py build ns1100
#   tools/test_bridgeif_ns.py build br-B1 ns1100
#   tools/test_default_firewall_ns.py build ns1100 br-B1

# Fetch command and arguments
cmd = sys.argv[1] if len(sys.argv) > 1 else None
namespace_name = "ns1100"
inbound=[
    {
        'version': 4,
        'source': '0.0.0.0/0',
        'destination': '10.0.0.2',
        'protocol': 'tcp',
        'port': '443, 80',
        'action': 'accept',
        'log': False,
        'order': 0,
    }, {
        'version': 4,
        'source': '2.3.4.5',
        'destination': '10.0.0.2',
        'protocol': 'tcp',
        'port': '22',
        'action': 'accept',
        'log': False,
        'order': 1,
    }, {
        'version': 6,
        'source': '2:3:4::/64',
        'destination': '5:6:7::/64',
        'protocol': 'icmp',
        'port': None,
        'action': 'accept',
        'log': False,
        'order': 2,
    }
]

outbound=[
    {
        'version': 4,  
        'source': '10.0.0.2',
        'destination': '1.2.3.0/24',
        'protocol': 'any',
        'port': 'any',
        'action': 'drop',
        'log': False,
        'order': 0,
    }, {
        'version': 4,  
        'source': '10.0.0.2',
        'destination': '0.0.0.0/0',
        'protocol': 'tcp',
        'port': '22-25, 5509',
        'action': 'drop',
        'log': False,
        'order': 1,
    }, {
        'version': 6,  
        'source': '1:2:3::/64',
        'destination': '5:6:7::/64',
        'protocol': 'icmp',
        'port': None,
        'action': 'drop',
        'log': False,
        'order': 2,
    },
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
    status, msg = project_firewall_ns.build(namespace_name, inbound, outbound, config_file)
elif cmd == 'read':
    status, data, msg = project_firewall_ns.read(namespace_name, config_file)
elif cmd == 'scrub':
    status, msg = project_firewall_ns.scrub(namespace_name, config_file)
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
