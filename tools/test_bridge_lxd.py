#!/usr/bin/env python3

import argparse
import json
import sys

from cloudcix_primitives import bridge_lxd

# Run the following test scripts before this one:
#
# * `tools/test_ns.py build mynetns to ensure the name space exists

def print_usage():
    print("""
Usage: test_bridge_lxd.py <command> <endpoint_url> <name> [--verify] [--debug]

Commands:
  build   - Create a bridge network
  read    - Read bridge network configuration
  scrub   - Delete a bridge network

Arguments:
  endpoint_url - The LXD endpoint URL
  name         - The bridge name
  --verify     - Verify LXD certificates (default: False)
  --debug      - Show more detailed output for debugging

Examples:
  # Create bridge (auto-discovers all cluster nodes)
  ./test_bridge_lxd.py build https://10.0.0.1:8443 br1002
  
  # Create bridge with certificate verification and debug output
  ./test_bridge_lxd.py build https://10.0.0.1:8443 br1002 --verify --debug
  
  # Read bridge configuration
  ./test_bridge_lxd.py read https://10.0.0.1:8443 br1002
  
  # Delete bridge
  ./test_bridge_lxd.py scrub https://10.0.0.1:8443 br1002
""")

# Create parser for command line arguments
parser = argparse.ArgumentParser(description='Test LXD bridge operations')
parser.add_argument('command', choices=['build', 'read', 'scrub'], help='Command to execute')
parser.add_argument('endpoint_url', help='LXD endpoint URL')
parser.add_argument('name', nargs='?', default='br1002', help='Bridge name')
parser.add_argument('--verify', action='store_true', help='Verify LXD certificates')
parser.add_argument('--debug', action='store_true', help='Show more detailed output')

# Show help if no arguments are provided
if len(sys.argv) == 1:
    print_usage()
    sys.exit(1)

# Parse arguments
args = parser.parse_args()

# Process arguments
cmd = args.command
endpoint_url = args.endpoint_url
name = args.name
verify_lxd_certs = args.verify
debug_mode = args.debug

# Set default config
config = {
    'ipv6.address': 'none',
    'ipv4.address': 'none',
}

# Execute command
status = None
msg = None
data = None

if cmd == 'build':
    print(f"Creating bridge '{name}' on endpoint '{endpoint_url}'")
    print(f"Certificate verification: {'Enabled' if verify_lxd_certs else 'Disabled'}")
    print("Auto-discovering all cluster nodes")
    
    if debug_mode:
        print(f"Config: {json.dumps(config, indent=2)}")
        
    status, msg = bridge_lxd.build(
        endpoint_url=endpoint_url, 
        name=name, 
        config=config, 
        verify_lxd_certs=verify_lxd_certs
    )
elif cmd == 'read':
    print(f"Reading bridge '{name}' from endpoint '{endpoint_url}'")
    print(f"Certificate verification: {'Enabled' if verify_lxd_certs else 'Disabled'}")
    
    status, data, msg = bridge_lxd.read(
        endpoint_url=endpoint_url, 
        name=name, 
        verify_lxd_certs=verify_lxd_certs
    )
elif cmd == 'scrub':
    print(f"Scrubbing bridge '{name}' from endpoint '{endpoint_url}'")
    print(f"Certificate verification: {'Enabled' if verify_lxd_certs else 'Disabled'}")
    
    status, msg = bridge_lxd.scrub(
        endpoint_url=endpoint_url, 
        name=name, 
        verify_lxd_certs=verify_lxd_certs
    )

# Display results
print("\nResults:")
print("--------")
print(f"Status: {status}")
print()
print("Message:")
if isinstance(msg, list):
    for item in msg:
        print(item)
else:
    print(msg)

if data is not None:
    print()
    print("Data:")
    print(json.dumps(data, indent=2) if isinstance(data, dict) else data)

# Print additional debugging help for failures
if not status and debug_mode:
    print("\nDebugging Tips:")
    print("--------------")
    print("1. Check if all nodes in the cluster are online and healthy")
    print("2. Verify that the specified nodes exist in the cluster")
    print("3. Check if any existing networks or bridges conflict")
    print("4. Try manually with: lxc network create {name} --target <node>")
    print("5. If using IPv6 URL, ensure your environment supports IPv6")
    
    # Print warning about SSL verification
    if not verify_lxd_certs:
        print("\nNote: You are running with SSL verification disabled.")
        print("This may generate warnings in your terminal output.")
        print("Use --verify to enable certificate verification if your certs are valid.")
