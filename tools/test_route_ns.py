import sys
import json
from cloudcix_primitives import route_ns

"""
Requirements

build ns -- python3 test_ns.py build maria
build bridgeif_ns -- python3 test_bridgeif_ns.py build frodo maria
build network_ns -- python3 test_network_ns.py build 'maria' '192.0.2.146' 'maria.frodo'

"""
# Fetch command and arguments
cmd = sys.argv[1] if len(sys.argv) > 1 else None
config_file = "/etc/cloudcix/pod/configs/config.json"
destination = "test_destination"
gateway = "test_gateway"
namespace = "testns"

if len(sys.argv) > 2:
    destination = sys.argv[2]
if len(sys.argv) > 3:
    gateway = sys.argv[3]
if len(sys.argv) > 4:
    namespace = sys.argv[4]

route = {'destination':destination , 'gateway': gateway}

status = None
msg = None
data = None

# Check and execute command
if cmd == 'build':
    status, msg = route_ns.build(namespace, route, config_file)
elif cmd == 'read':
    status, data, msg = route_ns.read(namespace, route, config_file)
elif cmd == 'scrub':
    status, msg = route_ns.scrub(namespace, route, config_file)
else:
   print(f"Unknown command: {cmd}")
   sys.exit(1)

# Output the status and messages
print("Status: %s" % status)
print("\nMessage:")
if isinstance(msg, list):
    for item in msg:
        print(item)
else:
    print(msg)

# Output data if available
if data is not None:
    print("\nData:")
    print(json.dumps(data, sort_keys=True, indent=4))
