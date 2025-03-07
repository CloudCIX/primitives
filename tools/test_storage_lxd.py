import json
import sys

from cloudcix_primitives import storage_lxd

# Run the following test scripts before this one:
#
# * `tools/test_ns.py build mynetns to ensure the name space we want exists
# * `tools/test_vlanif_ns.py build {vlan} to ensure vlan tagged interface exists on podnet
# * `tools/test_bridge_lxd.py build br4000 to ensure the LXD bridge exists to connect to the vlan tagged interface
# * `tools/test_lxd.py build to ensure the LXD container exists to modify the storage


cmd = sys.argv[1]

endpoint_url = None
new_size = '20GB'
project = 'mynetns'
name = 'mynetns-1234'
containers = 'containers'
verify_lxd_certs = False

if len(sys.argv) > 2:
    endpoint_url = sys.argv[2]

if len(sys.argv) > 3:
    new_size = sys.argv[3]

if len(sys.argv) > 4:
    project = sys.argv[4]

if len(sys.argv) > 5:
    name = sys.argv[5]

if endpoint_url is None:
    print('Endpoint URL is required, please supply the host as second argument.')
    exit()


if cmd == 'update':
    status, msg, successful_payloads = storage_lxd.update(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=name,
        new_size=new_size,
        containers=containers,  # Fixed: was using undefined instance_type variable
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
