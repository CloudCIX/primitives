#!/usr/bin/env python3

import sys

from cloudcix_primitives import config_set_lxd

cmd = sys.argv[1]
endpoint_url = None
name = 'mynetns-1234'
project = 'mynetns'
instance_type = 'virtual-machine'
verify_lxd_certs = False

if len(sys.argv) > 2:
    endpoint_url = sys.argv[2]
if endpoint_url is None:
    print('Endpoint URL is required, please supply the host as second argument.')
    exit()

status = None
msg = None

def test_update():
    config = {
        'security.csm': 'true',
        'security.secureboot': 'false',
    }
    status, msg = config_set_lxd.update(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=name,
        instance_type=instance_type,
        config=config,
        verify_lxd_certs=verify_lxd_certs,
    )
    print("Status: %s" % status)
    print()
    print("Message:")
    print(msg)

if cmd == 'update':
    test_update()
else:
    print(f"Unknown command: {cmd}")
    sys.exit(1)
