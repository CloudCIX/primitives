#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import cidata

# Run 
#
#   tools/test_directory_main.py build /etc/netns/mynetns/10.0.0.3/v1
#
# before this to ensure the directories needed
# are in place.

cmd = sys.argv[1]

config_file = "/etc/cloudcix/pod/configs/config.json"
domain_path = '/etc/netns/mynetns/cloudinit-metadata/10.0.0.3/v1'

metadata = {
  "instance-id": "mynetns_123",
  "network": {
    "version": 2,
    "ethernets": {
      "eth0": {
          "match": {
              "macaddress": "52:54:00:5d:4d:23"
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
  }
}

userdata = """
#!/bin/sh

echo "Cloud init user data payload did indeed get executed" > /root/message_from_cloudinit
cat /root/.ssh/authorized_keys >> /home/ubuntu/.ssh/authorized_keys
""".strip()

if len(sys.argv) > 2:
    domain_path = sys.argv[2]

if len(sys.argv) > 3:
    metadata_filename = sys.argv[3]
    f = open(metadata_filename)
    metadata = f.read()
    f.close()

if len(sys.argv) > 4:
    userdata_filename = sys.argv[4]
    open(userdata_filename)
    userdata = f.read()
    f.close()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = cidata.build(domain_path, metadata, userdata, config_file)
elif cmd == 'scrub':
    status, msg = cidata.scrub(domain_path, config_file)
elif cmd == 'read':
    status, data, msg = cidata.read(domain_path, config_file)
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

if data is not None:
    print()
    print("Data:")
    print(json.dumps(data, sort_keys=True, indent=4))
