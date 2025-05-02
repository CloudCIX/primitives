#!/usr/bin/env python
"""
Test script for vpnroute_ns primitive.

# Test just the read function
python test_vpnroute_ns.py read --namespace ns1234 --vpn-id 1234 --host 192.168.1.10 --username robot

# Test just the build function with specific networks
python test_vpnroute_ns.py build --namespace ns1234 --vpn-id 1234 --host 192.168.1.10 --username robot --networks 10.10.10.0/24 172.16.10.0/24

# Test all functions with custom settings
python test_vpnroute_ns.py all --namespace ns1234 --vpn-id 1234 --host 192.168.1.10 --username robot
"""
import sys
import os
import argparse
import json

# Add site-packages to Python path
SITE_PACKAGES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib', 'python3.13', 'site-packages')
sys.path.insert(0, SITE_PACKAGES_PATH)

# Import the necessary modules
try:
    from cloudcix_primitives.vpnroute_ns import build, read, scrub
    from cloudcix_primitives.utils import SSHCommsWrapper
    from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS
    print("Successfully imported required modules")
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

SUCCESS_CODE = 0

def print_separator():
    """Print a line separator for better readability"""
    print("-" * 80)

def setup_test_environment(namespace, vpn_id, device, host, username):
    """Set up the test environment by creating necessary namespace and XFRM interface"""
    print("\nSetting up test environment...")
    
    # Define all payloads upfront
    payloads = {
        'check_namespace': f"ip netns list | grep -w {namespace} || echo 'Namespace not found'",
        'create_namespace': f"ip netns add {namespace}",
        'check_xfrm_interface': f"ip netns exec {namespace} ip link show xfrm{vpn_id} 2>/dev/null || echo 'Interface does not exist'",
        'check_root_interface': f"ip link show | grep xfrm{vpn_id} || echo 'Not found'",
        'delete_root_interface': f"ip link delete xfrm{vpn_id}",
        'create_xfrm_interface': f"ip link add xfrm{vpn_id} type xfrm dev {device} if_id {vpn_id}",
        'disable_ipsec': f"sysctl -w net.ipv4.conf.xfrm{vpn_id}.disable_policy=1",
        'move_to_namespace': f"ip link set dev xfrm{vpn_id} netns {namespace}",
        'bring_up_interface': f"ip netns exec {namespace} ip link set dev xfrm{vpn_id} up"
    }
    
    rcc = SSHCommsWrapper(comms_ssh, host, username)
    
    # Check if namespace exists, create if not
    print("Checking if namespace exists...")
    ret = rcc.run(payloads['check_namespace'])
    
    if "Namespace not found" in ret["payload_message"]:
        print(f"Creating namespace '{namespace}'...")
        ret = rcc.run(payloads['create_namespace'])
        if ret["channel_code"] != CHANNEL_SUCCESS or ret["payload_code"] != 0:
            print(f"Failed to create namespace '{namespace}'. Exiting test.")
            print(f"Error: {ret['payload_error'] or ret['payload_message']}")
            return False
    
    # Check if XFRM interface exists in namespace
    print(f"Checking if XFRM interface xfrm{vpn_id} exists...")
    ret = rcc.run(payloads['check_xfrm_interface'])
    
    if "Interface does not exist" in ret["payload_message"]:
        print(f"Creating XFRM interface xfrm{vpn_id}...")
        
        # Check if interface exists in root namespace first
        ret = rcc.run(payloads['check_root_interface'])
        if "Not found" not in ret["payload_message"]:
            print(f"Interface xfrm{vpn_id} exists in root namespace. Deleting it first...")
            ret = rcc.run(payloads['delete_root_interface'])
        
        # Create new interface
        ret = rcc.run(payloads['create_xfrm_interface'])
        if ret["channel_code"] != CHANNEL_SUCCESS or ret["payload_code"] != 0:
            print(f"Failed to create XFRM interface. Exiting test.")
            print(f"Error: {ret['payload_error'] or ret['payload_message']}")
            return False
            
        # Disable IPsec policy
        ret = rcc.run(payloads['disable_ipsec'])
        if ret["channel_code"] != CHANNEL_SUCCESS or ret["payload_code"] != 0:
            print(f"Failed to disable IPsec policy. Exiting test.")
            print(f"Error: {ret['payload_error'] or ret['payload_message']}")
            return False
            
        # Move to namespace
        ret = rcc.run(payloads['move_to_namespace'])
        if ret["channel_code"] != CHANNEL_SUCCESS or ret["payload_code"] != 0:
            print(f"Failed to move interface to namespace. Exiting test.")
            print(f"Error: {ret['payload_error'] or ret['payload_message']}")
            return False
            
        # Bring interface up
        ret = rcc.run(payloads['bring_up_interface'])
        if ret["channel_code"] != CHANNEL_SUCCESS or ret["payload_code"] != 0:
            print(f"Failed to bring interface up. Exiting test.")
            print(f"Error: {ret['payload_error'] or ret['payload_message']}")
            return False
    
    print("Test environment setup complete!")
    return True

def main():
    """
    Main function to run tests for build, read, or scrub functions
    """
    parser = argparse.ArgumentParser(description='VPN Route testing in a namespace')
    parser.add_argument('action', choices=['build', 'read', 'scrub', 'all'], help='Action to perform')
    parser.add_argument('--namespace', '-n', default="testns", help='Project namespace (default: testns)')
    parser.add_argument('--vpn-id', '-v', type=int, default=6000, help='VPN identifier (default: 6000)')
    parser.add_argument('--host', '-H', default="10.0.0.1", help='Host to connect to (default: 10.0.0.1)')
    parser.add_argument('--username', '-u', default="robot", help='SSH username (default: robot)')
    parser.add_argument('--device', '-d', default="public0", help='Physical device to use (default: public0)')
    parser.add_argument('--networks', '-N', nargs='+', default=["192.168.100.0/24", "10.100.0.0/24"], 
                        help='List of network CIDRs (default: ["192.168.100.0/24", "10.100.0.0/24"])')
    parser.add_argument('--json', '-j', action='store_true', help='Output results in JSON format')
    parser.add_argument('--setup-only', action='store_true', help='Only set up the test environment without running tests')
    
    args = parser.parse_args()
    
    # Common parameters for all functions
    params = {
        'namespace': args.namespace,
        'vpn_id': args.vpn_id,
        'host': args.host,
        'username': args.username,
    }
    
    # Set up test environment
    if not setup_test_environment(args.namespace, args.vpn_id, args.device, args.host, args.username):
        print("Failed to set up test environment. Exiting.")
        sys.exit(1)
    
    if args.setup_only:
        print("Test environment setup completed. Exiting as requested.")
        sys.exit(0)
    
    results = {}
    
    # Execute the requested actions
    if args.action in ['build', 'all']:
        print_separator()
        print(f"TESTING BUILD OPERATION")
        print_separator()
        build_kwargs = params.copy()
        build_kwargs['networks'] = args.networks
        success, message = build(**build_kwargs)
        
        results['build'] = {"success": success, "message": message}
        
        if not args.json:
            print(f"Build result: {'SUCCESS' if success else 'FAILURE'}")
            print(f"Message: {message}")
    
    if args.action in ['read', 'all']:
        print_separator()
        print(f"TESTING READ OPERATION")
        print_separator()
        success, data, messages = read(**params)
        
        results['read'] = {"success": success, "data": data, "messages": messages}
        
        if not args.json:
            print(f"Read result: {'SUCCESS' if success else 'FAILURE'}")
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
                print("Error messages:")
                for msg in messages:
                    print(f"- {msg}")
    
    if args.action in ['scrub', 'all']:
        print_separator()
        print(f"TESTING SCRUB OPERATION")
        print_separator()
        success, message = scrub(**params)
        
        results['scrub'] = {"success": success, "message": message}
        
        if not args.json:
            print(f"Scrub result: {'SUCCESS' if success else 'FAILURE'}")
            print(f"Message: {message}")
    
    # Output JSON results if requested
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    
    # Determine exit code based on all test results
    all_success = all(result.get('success', False) for result in results.values())
    sys.exit(0 if all_success else 1)

if __name__ == "__main__":
    main()