#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import firewallns

namespace = "testns"
table = 'firewall_123'
nats = {
    'prerouting': {
        'priority': -100,
        'policy': 'accept',
        'conversions': [
            {'public': '185.49.60.116', 'private': '192.168.0.2', 'iface': 'testns.BM1'},
        ],
    },
    'postrouting': {
        'priority': 100,
        'policy': 'accept',
        'conversions': [
            {'private': '192.168.0.0/24', 'public': '185.49.60.117', 'iface': 'testns.BM1'},
        ],
    },
}
project_rules = [
    {
        'version': 4,
        'source': ['91.103.3.36', '91.20.3.0/24'],
        'destination': ['192.168.0.2'],
        'protocol': 'tcp',
        'port': ['80', '443', '22-25'],
        'action': 'accept',
        'log': True,
        'order': 1,
        'iiface': 'testns.BM1',
        'oiface': 'private0.1002',
    }, {
        'version': 4,
        'source': ['91.103.3.36', '91.20.3.0/24'],
        'destination': ['10.10.10.2'],
        'protocol': 'icmp',
        'port': [],
        'action': 'accept',
        'log': True,
        'order': 2,
        'iiface': 'testns.BM1',
        'oiface': 'private0.1002',
    }, {
        'version': 4,
        'source': ['@ie_ipv4'],
        'destination': ['10.10.10.2'],
        'protocol': 'icmp',
        'port': ['@myports'],
        'action': 'accept',
        'log': True,
        'order': 2,
        'iiface': 'testns.BM1',
        'oiface': 'private0.1002',
    },
]

geo_rules = [
    {
        'version': 4,
        'source': ['@ie_ipv4'],
        'destination': ['any'],
        'protocol': 'any',
        'port': [],
        'action': 'accept',
        'log': True,
        'order': 1,
        'iiface': 'testns.BM1',
        'oiface': '',
    }
]

sets = [
    {
        'name': 'ie_ipv4',
        'type': 'ipv4_addr',
        'elements': ['91.103.0.0/24'],
    }, {
        'name': 'myports',
        'type': 'inet_service',
        'elements': ['1-34', '589', '4434'],
    },
]

chains = {
    'prerouting': {
        'priority': 0,
        'policy': 'accept',
        'rules': geo_rules,
    },
    'forward': {
        'priority': 0,
        'policy': 'accept',
        'rules': project_rules,
    },
}

config_file = "/etc/cloudcix/pod/configs/config.json"

cmd = sys.argv[1]

if len(sys.argv) > 2:
    namespace = sys.argv[2]

if len(sys.argv) > 3:
    table = sys.argv[3]

if len(sys.argv) > 4:
    priority = int(sys.argv[4])

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = firewallns.build(namespace, table, chains, config_file, nats, sets)
if cmd == 'scrub':
    status, msg = firewallns.scrub(namespace, table, config_file)
if cmd == 'read':
    status, data, msg = firewallns.read(namespace, table, config_file)

print(f"Status: {status}")
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
