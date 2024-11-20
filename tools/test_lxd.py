#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import lxd

# Run the following test scripts before this one:
#
# * `tools/test_directorymain_primitive.py build /etc/netns/mynetns` to ensure the directories needed
#   are in place.
# * `tools/test_ns_primitive.py build mynetns to ensure the name space we want to run dhcpns in exists
# * `tools/test_bridge_lxd.py build br4000 to ensure the LXD bridge exists to connect to the vlan tagged interface
# * `tools/test_vlanifns_primitive.py build {vlan} to ensure vlan tagged interface exists on podnet
# * `tools/test_bridge_kvm_primitive.py build {vlan} to ensure vlan tagged interface exists on KVM Host

cmd = sys.argv[1]

endpoint_url = None
instance_type = 'container'
name = 'mynetns-1234'
project = 'mynetns'
image = {
	'os_variant': '24.04',
    'filename': 'https://cloud-images.ubuntu.com/releases',
}
cpu = 2
gateway_interface = {
	'vlan': 4000,
	'mac_address': '32:30:09:00:02:7a',
}
ram = 2
size = 50
secondary_interfaces = [],
verify_lxd_certs  =  False 

if len(sys.argv) > 2:
    endpoint_url = sys.argv[2]

if endpoint_url is None:
    print('Enpoint URL is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = lxd.build(
        endpoint_url=endpoint_url,
        project=project,
        name=name,
        instance_type=instance_type,
        image=image,
        cpu=cpu,
        gateway_interface=gateway_interface,
        ram=ram,
        size=size,
        secondary_interfaces=secondary_interfaces,
        verify_lxd_certs=verify_lxd_certs,
    )
if cmd == 'read':
    status, data, msg = lxd.read(domain=domain, host=host)

if cmd == 'quiesce':
    status, msg = lxd.quiesce(domain=domain, host=host)

if cmd == 'restart':
    status, msg = lxd.restart(domain=domain, host=host)

if cmd == 'scrub':
    status, msg = lxd.scrub(domain=domain, host=host)

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
