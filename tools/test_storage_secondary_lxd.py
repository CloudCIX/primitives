#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import storage_secondary_lxd

# Run the following test scripts before this one:
#
# * `tools/test_project_lxd.py build myproject https://127.0.0.1:8443` to create the LXD project
# * `tools/test_ns.py build mynetns` to ensure the name space exists
# * `tools/test_vlanif_ns.py build mynetns 1002` to ensure vlan tagged interface exists
# * `tools/test_bridge_lxd.py build https://127.0.0.1:8443 br1002` to ensure the LXD bridge exists
# * `tools/test_lxd.py build https://127.0.0.1:8443` to ensure the LXD instance exists
# * `tools/test_rbd_lxd.py build https://127.0.0.1:8443 myproject rbd secondary-vol 10 filesystem false` to create a storage volume

cmd = sys.argv[1]

endpoint_url = None
project = 'mynetns'
instance_name = 'mynetns-1234'
volume_name = 'secondary-vol'
mount_point = '/mnt/secondary'
instance_type = 'containers'
volume_type = 'filesystem'
storage_pool = 'default'
verify_lxd_certs = False

if len(sys.argv) > 2:
    endpoint_url = sys.argv[2]

if len(sys.argv) > 3:
    project = sys.argv[3]

if len(sys.argv) > 4:
    instance_name = sys.argv[4]

if len(sys.argv) > 5:
    volume_name = sys.argv[5]

if len(sys.argv) > 6:
    mount_point = sys.argv[6]

if len(sys.argv) > 7:
    volume_type = sys.argv[7]

if len(sys.argv) > 8:
    storage_pool = sys.argv[8]

if endpoint_url is None:
    print('Endpoint URL is required, please supply the host as second argument.')
    sys.exit(1)

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = storage_secondary_lxd.build(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=instance_name,
        volume_name=volume_name,
        mount_point=mount_point,
        instance_type=instance_type,
        volume_type=volume_type,
        verify_lxd_certs=verify_lxd_certs,
        storage_pool=storage_pool,
    )
elif cmd == 'read':
    status, msg, data = storage_secondary_lxd.read(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=instance_name,
        volume_name=volume_name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )
elif cmd == 'scrub':
    status, msg = storage_secondary_lxd.scrub(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=instance_name,
        volume_name=volume_name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )
else:
    print(f"Unknown command: {cmd}")
    sys.exit(1)

print("Status: %s" % status)
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
