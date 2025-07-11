import json
import sys

from cloudcix_primitives import ram_lxd

# Run the following test scripts before this one:
#
# * `tools/test_ns.py build mynetns to ensure the name space we want exists
# * `tools/test_vlanif_ns.py build {vlan} to ensure vlan tagged interface exists on podnet
# * `tools/test_bridge_lxd.py build br4000 to ensure the LXD bridge exists to connect to the vlan tagged interface
# * `tools/test_lxd.py build to ensure the LXD instance exists to modify the ram


cmd = sys.argv[1]

endpoint_url = None
ram = 6
project = 'mynetns'
name = 'mynetns-1234'
verify_lxd_certs = False 


if len(sys.argv) > 2:
    endpoint_url = sys.argv[2]

if len(sys.argv) > 3:
    ram = sys.argv[3]

if len(sys.argv) > 4:
    project = sys.argv[4]

if len(sys.argv) > 5:
    name = sys.argv[5]

if endpoint_url is None:
    print('Enpoint URL is required, please supply the host as second argument.')
    exit()


if cmd == 'update':
    status, msg = ram_lxd.update(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=name,
        ram=ram,
        verify_lxd_certs=verify_lxd_certs,
    )
else:
   print(f"Unknown command: {cmd}")
   sys.exit(1)


print("Status: %s" %  status)
print()
print("Message:")
if type(msg) == list:
    for item in msg:
        print(item)
else:
    print(msg)
