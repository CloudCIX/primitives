#!/usr/bin/env python3

import sys
from cloudcix_primitives import migrate_lxd

def print_usage():
    print("""
Usage: test_migrate_lxd.py build <endpoint_url> <target_cluster_member> [project] [instance_name]

Arguments:
  build                  - Command to trigger migration
  endpoint_url           - The LXD endpoint URL
  target_cluster_member  - The cluster node to migrate to
  project                - (Optional) LXD project name (default: mynetns)
  instance_name          - (Optional) Instance name (default: mynetns-1234)
""")

if len(sys.argv) < 4:
    print_usage()
    sys.exit(1)

cmd = sys.argv[1]
endpoint_url = sys.argv[2]
target_cluster_member = sys.argv[3]
project = sys.argv[4] if len(sys.argv) > 4 else 'mynetns'
name = sys.argv[5] if len(sys.argv) > 5 else 'mynetns-1234'
verify_lxd_certs = False  # Set to True if you want to verify certs

if cmd == 'build':
    status, msg = migrate_lxd.build(
        endpoint_url=endpoint_url,
        project=project,
        instance_name=name,
        target_cluster_member=target_cluster_member,
        instance_type='containers',
        verify_lxd_certs=verify_lxd_certs,
    )
else:
    print(f"Unknown command: {cmd}")
    print_usage()
    sys.exit(1)

print("Status: %s" % status)
print()
print("Message:")
if isinstance(msg, list):
    for item in msg:
        print(item)
else:
    print(msg)