#!/usr/bin/env python3
"""
This script provides a command-line interface to the vpnif_ns module
in the primitives.cloudcix_primitives package.

Example usage:
- Build a VPN interface:
  python test_vpnif_ns.py build --namespace ns1234 --vpn-id 6000 --host 192.168.1.10 --username robot --device public0

- Read a VPN interface status:
  python test_vpnif_ns.py read --namespace ns1234 --vpn-id 6000 --host 192.168.1.10 --username robot

- Remove a VPN interface:
  python test_vpnif_ns.py scrub --namespace ns1234 --vpn-id 6000 --host 192.168.1.10 --username robot
"""
import sys
import os

# Add site-packages to Python path
SITE_PACKAGES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib', 'python3.13', 'site-packages')
sys.path.insert(0, SITE_PACKAGES_PATH)

# Import the vpnif_ns module
try:
    from cloudcix_primitives.vpnif_ns import build, read, scrub
    print("Successfully imported vpnif_ns module")
except ImportError as e:
    print(f"Error importing vpnif_ns module: {e}")
    sys.exit(1)

if __name__ == "__main__":
    import argparse
    import json
    import sys
    
    parser = argparse.ArgumentParser(description='Direct test interface for VPN interface operations in a Project namespace')
    parser.add_argument('action', choices=['build', 'read', 'scrub'], help='Action to perform')
    parser.add_argument('--namespace', required=True, help='Project namespace')
    parser.add_argument('--vpn-id', required=True, type=int, help='VPN identifier')
    parser.add_argument('--host', required=True, help='Host to connect to')
    parser.add_argument('--username', required=True, help='Username for SSH connection')
    parser.add_argument('--device', default="public0", help='Physical device to use for the XFRM interface (default: public0)')
    parser.add_argument('--json', action='store_true', help='Output results in JSON format')
    
    args = parser.parse_args()
    
    # Map command line arguments to function parameters
    kwargs = {
        'namespace': args.namespace,
        'vpn_id': args.vpn_id,
        'host': args.host,
        'username': args.username,
        'device': args.device,
    }
    
    # Call the appropriate function based on the action argument
    if args.action == 'build':
        success, message = build(**kwargs)
        result = {"success": success, "message": message}
    elif args.action == 'read':
        success, data, messages = read(**kwargs)
        result = {
            "success": success,
            "data": data,
            "messages": messages
        }
    elif args.action == 'scrub':
        success, message = scrub(**kwargs)
        result = {"success": success, "message": message}
    
    # Output results
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        if args.action == 'read':
            print(f"Status: {'Success' if success else 'Failed'}")
            if success:
                print("\nData retrieved:")
                for host, host_data in data.items():
                    print(f"Host: {host}")
                    for key, value in host_data.items():
                        print(f"  {key}: {value}")
                print("\nMessages:")
                for msg in messages:
                    print(f"- {msg}")
            else:
                print("Messages:")
                for msg in messages:
                    print(f"- {msg}")
        else:
            print(f"Status: {'Success' if success else 'Failed'}")
            print(f"Message: {message}")
    
    sys.exit(0 if success else 1)