#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import bridge_lxd


cmd = sys.argv[1]

endpoint_url = None
name = 'br4000'
verify_lxd_certs = False
config = {
    'ipv6.address': 'none',
    'ipv4.address': 'none',
}

if len(sys.argv) > 2:
    endpoint_url = sys.argv[2]
if len(sys.argv) > 3:
    name = sys.argv[3]
if len(sys.argv) > 4:
    verify_lxd_certs = sys.argv[4]

if endpoint_url is None:
    print('Enpoint URL is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = bridge_lxd.build(endpoint_url=endpoint_url, name=name, config=config, verify_lxd_certs=verify_lxd_certs)
if cmd == 'scrub':
    status, msg = bridge_lxd.scrub(endpoint_url=endpoint_url, name=name, verify_lxd_certs=verify_lxd_certs)
if cmd == 'read':
    status, data, msg = bridge_lxd.read(endpoint_url=endpoint_url, name=name, verify_lxd_certs=verify_lxd_certs)

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
    print(data)
