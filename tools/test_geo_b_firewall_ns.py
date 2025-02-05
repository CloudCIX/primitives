#!/usr/bin/env python3

# stdlib
import sys
import json
# library
# local
from cloudcix_primitives import geo_b_firewall_ns

# Prerequisites for running this test script:
#
#   tools/test_ns.py build ns1100
#   tools/test_bridgeif_ns.py build br-B1 ns1100
#   Create one or more nftable sets with "ip netns exec ns1100 nft add set inet FILTER <name>_V4 '{ type ipv4_addr; flags interval; auto-merge; }'",
#   replacing V4 with V6 and ipv4_addr with ipv6_addr to test ipv6 path.

cmd = sys.argv[1] if len(sys.argv) > 1 else None
namespace_name = 'ns1100'
# these reference ipv4 sets that need to exist beforehand
inbound = ['IE_V4', 'GB_V6']
outbound = ['US_V6', 'JP_V4']
config_file = '/etc/cloudcix/pod/configs/config.json'

if len(sys.argv) > 2:
    namespace_name = sys.argv[2]
if len(sys.argv) > 3:
    inbound = sys.argv[3].split(',')
if len(sys.argv) > 4:
    outbound = sys.argv[4].split(',')

status = None
msg = None
data = None

if cmd == 'build': 
    status, msg = geo_b_firewall_ns.build(namespace_name, inbound, outbound, config_file)
else:
    print(f'Unknown command: {cmd}')
    sys.exit(1)


# Output the status and messages
print(f'Status: {status}')
print(f'\nMessage: {msg}')

# Output data if available
if data is not None:
    print('\nData:')
    print(json.dumps(data, sort_keys=True, indent=4))
