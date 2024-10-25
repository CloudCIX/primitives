#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import hyperv

# Run the following test scripts before this one:
# * `tools/test_directorymain_primitive.py build /etc/netns/mynetns/cloudcix-metadata` to ensure the directories needed
#   are in place.
#
# * `tools/test_ns_primitive.py build mynetns` to ensure the name space we want to run dhcpns in exists
#
# *  `tools/test_directory_hyperv_primitive.py build "D:\\HyperV\\myvm"`
#


cmd = sys.argv[1]

host = None
domain = '123_234'
image = 'WindowsServer-2019-Standard_Gen-2_v2.vhdx'
cpu = 2
ram = 2048  # must be in MBs
primary_storage = '123_234_HDD_568.vhdx'  # file extension must be in .vhdx or .vhd
size = 35  # must be in GBs
gateway_vlan = 1002
secondary_vlans = None
secondary_storages = None
robot_drive_url = None

if len(sys.argv) > 2:
    host = sys.argv[2]

if len(sys.argv) > 3:
    robot_drive_url = sys.argv[3]

if len(sys.argv) > 4:
    domain = sys.argv[4]

if len(sys.argv) > 5:
    size = sys.argv[5]

if len(sys.argv) > 6:
    cloudimage = sys.argv[6]

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    if robot_drive_url is None:
        print('`robot_drive_url` is required, please supply the host as third argument.')
        exit()
    status, msg = hyperv.build(
        host=host, domain=domain, size=size, primary_storage=primary_storage,
        image=image, cpu=cpu, ram=ram, gateway_vlan=gateway_vlan, secondary_vlans=secondary_vlans,
        secondary_storages=secondary_storages, robot_drive_url=robot_drive_url,
    )

if cmd == 'read':
    status, data, msg = hyperv.read(domain=domain, host=host)

if cmd == 'quiesce':
    status, msg = hyperv.quiesce(domain=domain, host=host)

if cmd == 'restart':
    status, msg = hyperv.restart(domain=domain, host=host)

if cmd == 'scrub':
    status, msg = hyperv.scrub(
        domain=domain, host=host, primary_storage=primary_storage,
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
