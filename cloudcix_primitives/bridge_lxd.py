"""
Primitive for Private Bridge in LXD
"""
# stdlib
import json
from typing import Tuple
# libs
from cloudcix.rcc import API_SUCCESS, CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper


__all__ = [
    'build',
    'read',
    'scrub',
]


def build(
    endpoint_url: str,
    name: int,
    config=None,
    verify_lxd_certs=True,
    cluster_nodes=None,
) -> Tuple[bool, str]:
    """
    description:
        Configures a bridge on the LXD host in a clustered environment.

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host where the service will be created
            type: string
            required: true
        name:
            description: The name of the bridge to create
            type: integer
            required: true
        config:
            description: |
                A dictionary for the additional configuration of the LXD bridge network.
                See https://documentation.ubuntu.com/lxd/en/latest/reference/network_bridge/#configuration-options
            type: object
            required: false
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
        cluster_nodes:
            description: |
                List of cluster node names to target when creating a bridge in a clustered environment.
                If not provided, all nodes in the cluster will be used.
            type: list
            required: false
        
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1000: f'Successfully created bridge_lxd {name} on {endpoint_url} cluster.',
        3021: f'Failed to connect to {endpoint_url} for networks.exists payload',
        3022: f'Failed to run networks.exists payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to connect to {endpoint_url} for networks.create payload',
        3024: f'Failed to run networks.create payload on {endpoint_url}. Payload exited with status ',
        3025: f'Failed to retrieve cluster nodes from {endpoint_url}',
        3026: f'Failed to stage network on cluster node ',
        3027: f'Failed to commit network configuration cluster-wide on {endpoint_url}',
    }

    rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
    fmt = HostErrorFormatter(
        endpoint_url,
        {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
        {},
    )
    prefix = 3020

    # Check if network already exists
    ret = rcc.run(cli='networks.exists', name=name)
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1])
    if ret["payload_code"] != API_SUCCESS:
        return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2])

    bridge_exists = ret['payload_message']
    fmt.add_successful('networks.exists', ret)

    if bridge_exists == False:
        # Fetch cluster nodes if not provided
        if cluster_nodes is None:
            ret = rcc.run(cli='cluster.members.get', api=True)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                error_detail = f" - Channel Error: {ret.get('channel_message', 'Unknown error')}"
                return False, f"{prefix+5}: {messages[prefix+5]}{error_detail}"
            if ret["payload_code"] != API_SUCCESS:
                error_detail = f" - Payload Error: {ret.get('payload_error', 'Unknown error')}"
                payload_msg = f" - Message: {ret.get('payload_message', 'No message')}"
                return False, f"{prefix+5}: {messages[prefix+5]}{error_detail}{payload_msg}"
            
            try:
                metadata = ret['payload_message']['metadata']
                cluster_nodes = [node['server_name'] for node in metadata]
            except (KeyError, TypeError) as e:
                return False, f"{prefix+5}: {messages[prefix+5]} - Invalid response format: {str(e)}"
        
        fmt.add_successful('cluster.members.get', ret)
        
        # Step 1: Stage the network on each node using direct API calls
        for node in cluster_nodes:
            # Create the network JSON for this specific node
            network_data = {
                "name": str(name),
                "description": f"Bridge network staged on {node}",
                "type": "bridge",
                "config": {}
            }
            
            # Use the direct API endpoint with target parameter
            ret = rcc.run(
                cli='networks.post', 
                api=True,
                json=network_data,
                params={"target": node}
            )
            
            if ret["channel_code"] != CHANNEL_SUCCESS:
                error_detail = f" - Channel Error: {ret.get('channel_message', 'Unknown error')}"
                return False, f"{prefix+6}: {messages[prefix+6]} {node} - {error_detail}"
            if ret["payload_code"] != API_SUCCESS:
                error_detail = f" - Payload Error: {ret.get('payload_error', 'Unknown error')}"
                payload_msg = f" - Message: {ret.get('payload_message', 'No message')}"
                return False, f"{prefix+6}: {messages[prefix+6]} {node} - {error_detail}{payload_msg}"
            
            fmt.add_successful(f'networks.create.stage.{node}', ret)
            
        # Step 2: Commit the final network configuration with full config
        final_network = {
            "name": str(name),
            "description": "Clustered bridge network",
            "type": "bridge",
            "config": config or {}
        }
        
        ret = rcc.run(
            cli='networks.post', 
            api=True,
            json=final_network
        )
        
        if ret["channel_code"] != CHANNEL_SUCCESS:
            error_detail = f" - Channel Error: {ret.get('channel_message', 'Unknown error')}"
            return False, f"{prefix+7}: {messages[prefix+7]}{error_detail}"
        if ret["payload_code"] != API_SUCCESS:
            error_detail = f" - Payload Error: {ret.get('payload_error', 'Unknown error')}"
            payload_msg = f" - Message: {ret.get('payload_message', 'No message')}"
            return False, f"{prefix+7}: {messages[prefix+7]}{error_detail}{payload_msg}"
        
        fmt.add_successful('networks.create.commit', ret)
    
    return True, messages[1000]



def read(endpoint_url: str,
    name: int,
    verify_lxd_certs=True,
) -> Tuple[bool, dict, list]:
    """
    description:
        Reads configuration of a bridge on the LXD host.

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host where the service will be read
            type: string
            required: true
        name:
            description: The name of the bridge to read
            type: integer
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
        
    return:
        description: |
            A tuple with a boolean flag stating if the read was successful or not,
            a dictionary containing the network data, and a list of messages.
        type: tuple
    """
    # Define message
    messages = {
        1200: f'Successfully read bridge_lxd {name} on {endpoint_url}.',
        3221: f'Failed to connect to {endpoint_url} for networks.get payload',
        3222: f'Failed to run networks.get payload on {endpoint_url}. Payload exited with status ',
    }

    # Initialize data structures
    data_dict = {}
    data_dict[endpoint_url] = {}
    message_list = []
    prefix = 3220

    # Create LXD wrapper and formatter
    rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
    fmt = HostErrorFormatter(
        endpoint_url,
        {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
        {},
    )

    # Use proper API call to get network information
    ret = rcc.run(cli=f'networks["{name}"].get', api=True)
    
    if ret["channel_code"] != CHANNEL_SUCCESS:
        error_detail = f" - Channel Error: {ret.get('channel_message', 'Unknown error')}"
        message_list.append(f"{prefix+1}: {messages[prefix+1]}{error_detail}")
        return False, data_dict, message_list
    
    if ret["payload_code"] != API_SUCCESS:
        error_detail = f" - Payload Error: {ret.get('payload_error', 'Unknown error')}"
        payload_msg = f" - Message: {ret.get('payload_message', 'No message')}"
        message_list.append(f"{prefix+2}: {messages[prefix+2]}{error_detail}{payload_msg}")
        return False, data_dict, message_list
    
    # Store the network data
    try:
        # The API already returns a Python dict/object, so no need to parse JSON
        network_info = ret["payload_message"]
        
        # Create a serializable representation of the network data
        if isinstance(network_info, dict):
            # If it's already a dict, use it directly
            serializable_data = network_info
        else:
            # Otherwise, create a simpler representation
            serializable_data = {
                "name": str(name),
                "type": getattr(network_info, "type", "unknown"),
                "description": getattr(network_info, "description", ""),
                "config": getattr(network_info, "config", {}),
                "managed": getattr(network_info, "managed", True),
                "used_by": getattr(network_info, "used_by", [])
            }
        
        data_dict[endpoint_url]['network'] = serializable_data
    except Exception as e:
        # If anything fails, store a simple error representation
        data_dict[endpoint_url]['network'] = {
            "name": str(name),
            "error": f"Failed to process network data: {str(e)}"
        }
    
    fmt.add_successful('networks.get', ret)
    
    return True, data_dict, [messages[1200]]


def scrub(
    endpoint_url: str,
    name: int,
    verify_lxd_certs=True,
) -> Tuple[bool, str]:
    """
    description:
        Scrubs a bridge on the LXD host.

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host where the service will be scrubbed
            type: string
            required: true
        name:
            description: The name of the bridge to scrub
            type: integer
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
        
    return:
        description: |
            A tuple with a boolean flag stating if the scrub was successful or not and
            the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1100: f'Successfully scrubbed bridge_lxd {name} on {endpoint_url}.',
        3121: f'Failed to connect to {endpoint_url} for networks.exists payload',
        3122: f'Failed to run networks.exists payload on {endpoint_url}. Payload exited with status ',
        3123: f'Failed to connect to {endpoint_url} for networks["{name}"].delete payload',
        3124: f'Failed to run networks["{name}"].delete payload on {endpoint_url}. Payload exited with status ',
    }

    rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
    fmt = HostErrorFormatter(
        endpoint_url,
        {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
        {},
    )
    prefix = 3120

    ret = rcc.run(cli='networks.exists', name=name)
    if ret["channel_code"] != CHANNEL_SUCCESS:
        error_detail = f" - Channel Error: {ret.get('channel_message', 'Unknown error')}"
        return False, f"{prefix+1}: {messages[prefix+1]}{error_detail}"
    if ret["payload_code"] != API_SUCCESS:
        error_detail = f" - Payload Error: {ret.get('payload_error', 'Unknown error')}"
        return False, f"{prefix+2}: {messages[prefix+2]}{error_detail}"

    bridge_exists = ret['payload_message']
    fmt.add_successful('networks.exists', ret)

    if bridge_exists == True:
        ret = rcc.run(cli=f'networks["{name}"].delete', api=True)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            error_detail = f" - Channel Error: {ret.get('channel_message', 'Unknown error')}"
            return False, f"{prefix+3}: {messages[prefix+3]}{error_detail}"
        if ret["payload_code"] != API_SUCCESS:
            error_detail = f" - Payload Error: {ret.get('payload_error', 'Unknown error')}"
            payload_msg = f" - Message: {ret.get('payload_message', 'No message')}"
            return False, f"{prefix+4}: {messages[prefix+4]}{error_detail}{payload_msg}"
    
    return True, messages[1100]
