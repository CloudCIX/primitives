#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import lxd

# Run the following test scripts before this one:
#
# * `tools/test_directorymain_primitive.py build /etc/netns/mynetns` to ensure the directories needed
#   are in place.
# * `tools/test_ns_primitive.py build mynetns to ensure the name space we want to run dhcpns in exists
# * `tools/test_vlanifns_primitive.py build {vlan} to ensure vlan tagged interface exists on podnet
# * `tools/test_bridge_lxd.py build br4000 to ensure the LXD bridge exists to connect to the vlan tagged interface
# * `tools/test_bridge_kvm_primitive.py build {vlan} to ensure vlan tagged interface exists on KVM Host

cmd = sys.argv[1]

endpoint_url = None
instance_type = 'containers'
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
secondary_interfaces = []
verify_lxd_certs  =  False 

network_config = """
"version": 2
"ethernets": {
  "eth0": {
      "match": {
          "macaddress": "00:16:3e:f0:cc:45"
      },
      "addresses" : [
         "10.0.0.3/24"
      ],
      "nameservers": {
          "addresses": ["8.8.8.8"],
          "search": ["cloudcix.com", "cix.ie"]
      },
      "routes": [{
        "to": "default",
        "via": "10.0.0.1"
      }
    ]
  }
}
"""

userdata = """
#cloud-config
hostname: test-lxd-primitive

users:
  - name: administrator
    groups: sudo
    passwd:  $6$rand5Alt$v..Ygd5dbiOaR60Zan0U0HQyGdFAxIp0s/BSRdTS7x2ALGTHrT8Km1S41YutublfLAvDUpsAzI7WIjMuGNkKY0
    lock_passwd: false
    shell: /bin/bash

write_files:
  - path: /home/administrator/hello.txt
    permissions: "0644"
    content: |
      Hello World!

runcmd:
  - apt-get update
  - apt-get install python3-pip python3-venv git --yes
  - cd /home/administrator/
  - git clone https://github.com/CloudCIX/primitives.git
  - python3 -m venv .venv/
  - .venv/bin/pip install -r primitives/requirements.txt
"""

if len(sys.argv) > 2:
    endpoint_url = sys.argv[2]
if len(sys.argv) > 3:
    gateway_interface['vlan'] = sys.argv[3]

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
        network_config=network_config,
        userdata=userdata,
        secondary_interfaces=secondary_interfaces,
        verify_lxd_certs=verify_lxd_certs,
    )
if cmd == 'read':
    status, data, msg = lxd.read(
        endpoint_url=endpoint_url,
        project=project,
        name=name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )

if cmd == 'quiesce':
    status, msg = lxd.quiesce(
        endpoint_url=endpoint_url,
        project=project,
        name=name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )
if cmd == 'restart':
    status, msg = lxd.restart(
        endpoint_url=endpoint_url,
        project=project,
        name=name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )

if cmd == 'scrub':
    status, msg = lxd.scrub(
        endpoint_url=endpoint_url,
        project=project,
        name=name,
        instance_type=instance_type,
        verify_lxd_certs=verify_lxd_certs,
    )

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
