#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import bridge_lxd


cmd = sys.argv[1]

host = None
name = 'br4000'
verify_lxd_certs = False

if len(sys.argv) > 2:
    host = sys.argv[2]
if len(sys.argv) > 3:
    name = sys.argv[3]
if len(sys.argv) > 4:
    verify_lxd_certs = sys.argv[4]

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = bridge_lxd.build(host=host, name=name, verify_lxd_certs=verify_lxd_certs)
# if cmd == 'scrub':
#     status, msg = bridge_lxd.scrub(host=host, name=name, verify_lxd_certs=verify_lxd_certs)
# if cmd == 'read':
#     status, data, msg = bridge_lxd.read(host=host, name=name, verify_lxd_certs=verify_lxd_certs)

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
