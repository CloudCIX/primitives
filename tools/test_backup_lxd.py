#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import backup_lxd

# Run the following test scripts before this one:
#
# * `tools/test_lxd.py build` to ensure the LXD instance exists to create backups for

cmd = sys.argv[1]

host = None
instance_name = 'test'
backup_id = 'backup001'
backup_dir = '/home/robot/lxd_backups'
instance_type = 'virtual-machines'
username = 'robot'

if len(sys.argv) > 2:
    host = sys.argv[2]

if len(sys.argv) > 3:
    instance_name = sys.argv[3]

if len(sys.argv) > 4:
    backup_id = sys.argv[4]

if len(sys.argv) > 5:
    backup_dir = sys.argv[5]

if len(sys.argv) > 6:
    instance_type = sys.argv[6]

if len(sys.argv) > 7:
    username = sys.argv[7]

if host is None:
    print('Host is required, please supply the host as second argument.')
    exit()

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = backup_lxd.build(
        host=host,
        instance_name=instance_name,
        backup_id=backup_id,
        backup_dir=backup_dir,
        instance_type=instance_type,
        username=username,
    )
elif cmd == 'read':
    status, data, msg = backup_lxd.read(
        host=host,
        instance_name=instance_name,
        backup_id=backup_id,
        backup_dir=backup_dir,
        instance_type=instance_type,
        username=username,
    )
elif cmd == 'scrub':
    status, msg = backup_lxd.scrub(
        host=host,
        instance_name=instance_name,
        backup_id=backup_id,
        backup_dir=backup_dir,
        instance_type=instance_type,
        username=username,
    )
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