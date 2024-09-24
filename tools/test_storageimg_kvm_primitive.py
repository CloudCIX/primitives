#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import storageimg_kvm

cmd = sys.argv[1]

host = '2a02:2078:9::30:0:8'
domain_path = '/var/lib/libvirt/images/'
storage = '123_234_HDD_567.img'
size = 20
update_size = 30
cloudimage = '/var/lib/libvirt/ISOs/KVM/ISOs/noble-server-cloudimg-amd64.img'

if len(sys.argv) > 2:
    storage = sys.argv[2]

if len(sys.argv) > 3:
    size = sys.argv[3]

if len(sys.argv) > 4:
    cloudimage = sys.argv[4]

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = storageimg_kvm.build(
        host=host, domain_path=domain_path, storage=storage, size=size, cloudimage=cloudimage
    )
if cmd == 'update':
    status, msg = storageimg_kvm.update(
        host=host, domain_path=domain_path, storage=storage, size=update_size
    )
if cmd == 'scrub':
    status, msg = storageimg_kvm.scrub(host=host, domain_path=domain_path, storage=storage)
if cmd == 'read':
    status, data, msg = storageimg_kvm.read(host=host, domain_path=domain_path, storage=storage)

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
