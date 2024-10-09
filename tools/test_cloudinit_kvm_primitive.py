#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import cloudinit_kvm

cmd = sys.argv[1]


host = None
domain = '123_234'
domain_path = '/var/lib/libvirt/images/'
cloudimage = '/var/lib/libvirt/ISOs/KVM/IMGs/noble-server-cloudimg-amd64-cloudcix.img'
cpu = 2
ram = 2048  # must be in MBs
primary_storage = '123_234_HDD_568.img'
size = 20
osvariant = 'generic'
gateway_interface = {
    'mac_address': 'aa:bb:cc:dd:ee:f0',
    'vlan_bridge': 'br1000',
}
secondary_interfaces = None,
secondary_storages = None,

if len(sys.argv) > 2:
    host = sys.argv[2]

if len(sys.argv) > 3:
    domain = sys.argv[3]

if len(sys.argv) > 4:
    size = sys.argv[4]

if len(sys.argv) > 5:
    cloudimage = sys.argv[5]

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = cloudinit_kvm.build(
        host=host, domain_path=domain_path, domain=domain, size=size, primary_storage=primary_storage,
        cloudimage=cloudimage, cpu=cpu, ram=ram, osvariant=osvariant, gateway_interface=gateway_interface,
    )

if cmd == 'read':
    status, data, msg = cloudinit_kvm.read(domain=domain, host=host)

if cmd == 'quiesce':
    status, data, msg = cloudinit_kvm.quiesce(domain=domain, host=host)

if cmd == 'restart':
    status, data, msg = cloudinit_kvm.restart(domain=domain, host=host)

if cmd == 'scrub':
    status, data, msg = cloudinit_kvm.scrub(
        domain=domain, host=host, domain_path=domain_path, primary_storage=primary_storage,
    )

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
