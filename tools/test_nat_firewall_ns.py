#!/usr/bin/env python3

import sys
import json
from cloudcix_primitives import nat_firewall_ns

# Prerequisites for running this test script:
#
#   tools/test_ns.py build ns1100
#   tools/test_bridgeif_ns.py build br-B1 ns1100
#   tools/test_default_firewall_ns.py build ns1100 br-B1

# Fetch command and arguments
cmd = sys.argv[1] if len(sys.argv) > 1 else None
namespace_name = "ns1100"
one_to_one = [
        {'private': '10.0.0.10', 'public': '185.49.60.109'},
        {'private': '10.0.0.20', 'public': '185.49.60.45'},
    ]
ranges = ['10.0.0.0/24', '172.16.10.0/24']
public_ip_ns='185.49.60.108'

config_file = "/etc/cloudcix/pod/configs/config.json"

if len(sys.argv) > 2:
    namespace_name = sys.argv[2]
if len(sys.argv) > 3:
    one_to_one = json.loads(sys.argv[3])
if len(sys.argv) > 3:
    ranges = json.loads(sys.argv[4])
if len(sys.argv) > 4:
    ranges = json.loads(sys.argv[5])


status = None
msg = None
data = None

# Check and execute command
if cmd == 'build':
    status, msg = nat_firewall_ns.build(namespace_name, one_to_one, ranges, public_ip_ns, config_file)
elif cmd == 'read':
    status, data, msg = nat_firewall_ns.read(namespace_name, config_file)
elif cmd == 'scrub':
    status, msg = nat_firewall_ns.scrub(namespace_name, config_file)
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
