#! /usr/bin/env python3

# stdlib
import sys
import json
# local
from cloudcix_primitives import set_firewall_ns

# Prerequisites for running this test script:
#
#   tools/test_ns.py build ns1100
#   tools/test_bridgeif_ns.py build br-B1 ns1100
#   tools/test_default_firewall_ns.py ns1100 br-B1

cmd = sys.argv[1] if len(sys.argv) > 1 else None
set_name = "IE_41"
namespace_name = "ns1100"
set_type = 'ipv4_addr'
set_elements = '8.8.8.8, 1.1.1.1, 192.168.0.1/24'
config_file = "/etc/cloudcix/pod/configs/config.json"

if len(sys.argv) > 2:
    namespace_name = sys.argv[2]
if len(sys.argv) > 3:
    set_name = sys.argv[3]
if len(sys.argv) > 4:
    # Depending on whether the operation is 'build' or 'update', the 3rd
    # argument is either the set's type or its list of elements.
    set_type = sys.argv[4]
    set_elements = sys.argv[4]

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = set_firewall_ns.build(namespace_name, set_name, set_type, config_file)
elif cmd == 'scrub':
    status, msg = set_firewall_ns.scrub(namespace_name, set_name, config_file)
elif cmd == 'update': 
    status, msg = set_firewall_ns.update(namespace_name, set_name, set_elements, config_file)
else:
    print(f'Unknown command: {cmd}')
    sys.exit(1)

print(f'Status: {status}')
print(f'\nMessage: {msg}')

if data is not None:
    print(f'\nData: {json.dumps(data, sort_keys=True, indent=4)}')
