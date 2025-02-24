#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import hyperv

# Run the following test scripts before this one:
# * `tools/test_ns.py build mynetns` to ensure the name space exists
# * `tools/test_vlanif_ns.py build {vlan} to ensure vlan tagged interface exists on podnet



cmd = sys.argv[1]

host = None
region_url = None
vm_identifier = '123_234'
storage_identifier = 'HDD_234.vhdx'
image = 'WindowsServer-2019-Standard_Gen-2_v2.vhdx'
administrator_password = 'cloudcix'
cpu = 2
ram = 2 
gb = 50 

gateway_network = {
    'vlan': 1002,
    'ips': [{
        'ip': '',
        'netwask': '',
        'gateway': '',
        'dns': '',
    }]
}
secondary_networks = []
local_mount_path = '/etc/cloudcix/robot/'

if len(sys.argv) > 2:
    host = sys.argv[2]

if len(sys.argv) > 3:
    region_url = sys.argv[3]

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

if region_url is None:
    print('region_url is required, please supply the region_url as third argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    if region_url is None:
        print('`region_url` is required, please supply the host as third argument for build.')
        exit()
    status, msg = hyperv.build(
        host=host,
        vm_identifier=vm_identifier,
        storage_identifier=storage_identifier,
        image=image,
        administrator_password=administrator_password,
        cpu=cpu,
        ram=ram,
        gb=gb,
        region_url=region_url,
        gateway_network=gateway_network,
        secondary_networks=secondary_networks,
        local_mount_path=local_mount_path,     
    )
elif cmd == 'quiesce':
    status, msg = hyperv.quiesce(host=host, vm_identifier=vm_identifier)
elif cmd == 'read':
    status, data, msg = hyperv.read(host=host, vm_identifier=vm_identifier)
elif cmd == 'restart':
    status, msg = hyperv.restart(host=host, vm_identifier=vm_identifier)
elif cmd == 'scrub':
    status, msg = hyperv.scrub(host=host, vm_identifier=vm_identifier, storage_identifier=storage_identifier)
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
