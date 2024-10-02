#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import cloudinit_kvm

cmd = sys.argv[1]


gateway_interface: dict,
primary_storage: str,
secondary_interfaces = None,
secondary_storages = None,




host = None
domain = '123_234'
domain_path = '/var/lib/libvirt/images/'
cloudimage = '/var/lib/libvirt/ISOs/KVM/IMGs/'
cpu = 2
ram = 2048  # must be in MBs
storage = '123_234_HDD_568.img'
size = 20
osvariant = 'generic'


if len(sys.argv) > 2:
    host = sys.argv[2]

if len(sys.argv) > 3:
    storage = sys.argv[3]

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
    status, msg = storage_kvm.build(
        host=host, domain_path=domain_path, storage=storage, size=size
    )
if cmd == 'update':
    status, msg = storage_kvm.update(
        host=host, domain_path=domain_path, storage=storage, size=update_size
    )
if cmd == 'scrub':
    status, msg = storage_kvm.scrub(host=host, domain_path=domain_path, storage=storage)
if cmd == 'read':
    status, data, msg = storage_kvm.read(host=host, domain_path=domain_path, storage=storage)

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
