#!/usr/bin/env python3

# stdlib
import sys
import json
# library
# local
from cloudcix_primitives import geo_b_firewall_ns

cmd = sys.argv[1] if len(sys.argv) > 1 else None
namespace_name = 'ns1100'
inbound = ['IE_V4', 'GB_V5']
outbound = ['US_V1', 'JP_V2']
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
