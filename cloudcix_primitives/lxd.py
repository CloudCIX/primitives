"""
Primitive for managing an LXD instance.
"""
# stdlib
from typing import Tuple
# libs
from cloudcix.rcc import API_SUCCESS, CHANNEL_SUCCESS, comms_lxd
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper


__all__ = [
    'build',
    'quiesce',
    'read',
    'restart',
    'scrub',
]


def build(
    endpoint_url: str,
    project: str,
    instance_name: str,
    image: dict,
    cpu: int,
    gateway_interface: dict,
    ram: int,
    size: int,
    network_config: str,
    userdata: str,
    secondary_interfaces=[],
    instance_type: str = "container",
    verify_lxd_certs=True,
) -> Tuple[bool, str]:
    """
    description:
        Configures a LXD instance on the LXD host.

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host where the service will be built.
            type: string
            required: true
        project: 
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        instance_name:
            description: Unique identification name for the LXD instance on the LXD Host.
            type: string
            required: true
        image:
            type: object
            properties:
                os_variant:
                    description: The OS Variant of the image to install e.g. 24.04
                    type: string
                    required: true
                filename:
                    description: The URL for the simplestram server to pull the image from e.g. https://cloud-images.ubuntu.com/releases
                    type: string
                    required: true
        cpu:
            description: CPU property of the LXD instance
            type: integer
            required: true
        gateway_interface:
            type: object
            properties:
                device_identifier:
                    description: The device identifier of network device fro the gateway interface for the LXD instance e.g. eth0
                    type: string
                    required: true
                vlan:
                    description: The VLAN ID of the gateway interface for the LXD instance
                    type: string
                    required: true
                mac_address:
                    description: The MAC address of the the gateway interface for the LXD instance
                    type: string
                    required: true
        ram: 
            description: RAM property of the LXD instance, must be in GBs
            type: integer
            required: true
        size:
            description: The size of the storage image to be created, must be in GB value
            type: integer
            required: true
        network_config: 
            description: |
                The network details of the interfaces for the LXD instance e.g.
                '''
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
                '''
            type: string
            required: true
        userdata: 
            description: The cloudinit userdata for the LXD instance
            type: string
            required: true
        secondary_interfaces:
            type: array
            items:
                type: object
                properties:
                    device_identifier:
                        description: The device identifier of network device fro the gateway interface for the LXD instance e.g. eth1
                        type: string
                        required: true
                    vlan:
                        description: The VLAN ID of the interface for the LXD instance
                        type: string
                        required: true
                    mac_address:
                        description: The MAC address of the the interface for the LXD instance
                        type: string
                        required: true
        instance_type:
            description: The type of LXD instance to create - "container" or "virtual-machine"
            type: string
            required: false
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1000: f'Successfully created {instance_type} {instance_name} on {endpoint_url}',
        3021: f'Failed to connect to {endpoint_url} for projects.exists payload',
        3022: f'Failed to run projects.exists payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to connect to {endpoint_url} for projects.create payload',
        3024: f'Failed to run projects.create payload on {endpoint_url}. Payload exited with status ',
        3025: f'Failed to connect to {endpoint_url} for instances.exists payload',
        3026: f'Failed to run instances.exists payload on {endpoint_url}. Payload exited with status ',
        3027: f'Failed to connect to {endpoint_url} for instances.create payload',
        3028: f'Failed to run instances.create payload on {endpoint_url}. Payload exited with status ',
    }

    # Validate instance type
    if instance_type not in ["container", "virtual-machine"]:
        return False, f"Invalid instance_type: {instance_type}. Must be 'container' or 'virtual-machine'"

    # validation
    config = {
        'name': instance_name,
        'architecture': 'x86_64',
        'profiles': ['default'],
        'ephemeral': False,
        'type': instance_type,  # Add instance type to config
        'config': {
            'limits.cpu': f'{cpu}',
            'limits.memory': f'{ram}GB',
            'cloud-init.network-config': network_config,
            'cloud-init.user-data': userdata,
        },
        'devices': {
            'root': {
                'type': 'disk',
                'path': '/',
                'pool': 'local',
                'size': f'{size}GB',
            },
            gateway_interface['device_identifier']: {
                'type': 'nic',
                'network': f'br{gateway_interface["vlan"]}',
                'ipv4.address': None,
                'ipv6.address': None,
            }
        },
        'source': {
            'type': 'image',
            'alias': image['os_variant'],
            'mode': 'pull',
            'protocol': 'simplestreams',
            'server': image['filename'],
        },
    }
    if gateway_interface['mac_address']:
        config['config'][f'volatile.{gateway_interface["device_identifier"]}.hwaddr'] = gateway_interface['mac_address']

    if len(secondary_interfaces) > 0:
        for interface in secondary_interfaces:
            device_identifier = interface['device_identifier']
            config['devices'][device_identifier] = {
                'type': 'nic',
                'network': f'br{interface["vlan"]}',
                'ipv4.address': None,
                'ipv6.address': None,
            }
            if interface['mac_address']:
                config['config'][f'volatile.{device_identifier}.hwaddr'] = interface['mac_address']

    def run_host(endpoint_url, prefix, successful_payloads):

        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Check if LXD Project exists on host
        ret = rcc.run(cli=f'projects.exists', name=project)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads

        project_exists = ret['payload_message']
        if project_exists == False:
            # Create LXD Project on host
            ret = rcc.run(cli=f'projects.create', name=project)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            if ret["payload_code"] != API_SUCCESS:
                return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads

        # Check if instances exists in Project
        ret = project_rcc.run(cli='instances.exists', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads

        instance_exists = ret['payload_message']
        fmt.add_successful('instances.exists', ret)

        if instance_exists == False:
            # Build instance in Project
            ret = project_rcc.run(cli='instances.create', config=config, wait=True)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            if ret["payload_code"] != API_SUCCESS:
                return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads

            # Start the instance.
            instance = ret['payload_message']
            instance.start(wait=True)
        
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'


def quiesce(endpoint_url: str, project: str, instance_name: str, instance_type: str, verify_lxd_certs=True) -> Tuple[bool, str]:
    """
    description: Shutdown the LXD Instance

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host where the service will be quiesced.
            type: string
            required: true
        project: 
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        instance_name:
            description: Unique identification name for the LXD instance on the LXD Host.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance - "container" or "virtual-machine"
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false

    return:
        description: |
            A tuple with a boolean flag stating the quiesce was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1400: f'Successfully quiesced {instance_type} {instance_name} on {endpoint_url}',

        3421: f'Failed to connect to {endpoint_url} for instances.get payload',
        3422: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
        3423: f'Failed to quiesce instance on {endpoint_url}. Instance was found in an unexpected state of ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):

        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get instances client obj
        ret = project_rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        # Stop the instance.
        instance = ret['payload_message']
        state = instance.state()
        if state.status == 'Running':
            instance.stop(force=False, wait=True)
        elif state.status != 'Stopped':
            return False, f"{prefix+3}: {messages[prefix+3]} {state.status}"

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3420, {})
    if status is False:
        return status, msg

    return True, f'1400: {messages[1400]}'


def read(endpoint_url: str, project: str, instance_name: str, instance_type: str, verify_lxd_certs=True) -> Tuple[bool, str]:
    """
    description:
        Reads a instance on the LXD host.

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host where the service will be read.
            type: string
            required: true
        project: 
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        instance_name:
            description: Unique identification name for the LXD instance on the LXD Host.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance - "container" or "virtual-machine"
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false
        
    return:
        description: |
            A tuple with a boolean flag stating if the read was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1200: f'Successfully read {instance_type} instance {instance_name} on {endpoint_url}.',
        3221: f'Failed to connect to {endpoint_url} for instances.get payload',
        3222: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads, data_dict):
        retval = True
        data_dict[endpoint_url] = {}

        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        ret = project_rcc.run(cli=f'instances["{instance_name}"].get', api=True)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1}: " + messages[prefix+1])
        elif ret["payload_code"] != API_SUCCESS:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2}: " + messages[prefix+2])
        else:
            data_dict[endpoint_url][f'instances["{instance_name}"].get'] = ret["payload_message"].json()
            fmt.add_successful(f'instances["{instance_name}"].get', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(endpoint_url, 3220, {}, {})
    message_list = list()
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, f'1200: {messages[1200]}'


def restart(endpoint_url: str, project: str, instance_name: str, instance_type: str, verify_lxd_certs=True) -> Tuple[bool, str]:
    """
    description: Restart the LXD Instance

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host where the service will be restarted.
            type: string
            required: true
        project: 
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        instance_name:
            description: Unique identification name for the LXD instance on the LXD Host.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance - "container" or "virtual-machine"
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false

    return:
        description: |
            A tuple with a boolean flag stating the restart was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1500: f'Successfully restarted {instance_type} {instance_name} on {endpoint_url}',

        3521: f'Failed to connect to {endpoint_url} for instances.get payload',
        3522: f'Failed to run instances.get payload on {endpoint_url}. Payload exited with status ',
        3523: f'Failed to restart instance on {endpoint_url}. Instance was found in an unexpected state of ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):

        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get instances client obj
        ret = project_rcc.run(cli=f'instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        # Stop the instance.
        instance = ret['payload_message']
        state = instance.state()
        if state.status == 'Stopped':
            instance.start(force=False, wait=True)
        elif state.status != 'Running':
            return False, f"{prefix+3}: {messages[prefix+3]} {state.status}"

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3520, {})
    if status is False:
        return status, msg

    return True, f'1500: {messages[1500]}'


def scrub(endpoint_url: str, project: str, instance_name: str, instance_type: str, verify_lxd_certs=True) -> Tuple[bool, str]:
    """
    description: Scrub the LXD Instance

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host where the service will be scrubbed.
            type: string
            required: true
        project: 
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        instance_name:
            description: Unique identification name for the LXD instance on the LXD Host.
            type: string
            required: true
        instance_type:
            description: The type of LXD instance - "container" or "virtual-machine"
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false

    return:
        description: |
            A tuple with a boolean flag stating the scrub was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1100: f'Successfully scrubbed {instance_type} {instance_name} on {endpoint_url}',

        3121: f'Failed to connect to {endpoint_url} for instances.get payload',
        3122: f'Failed to connect to {endpoint_url} for instances.all payload',
        3123: f'Failed to run instances.all payload on {endpoint_url}. Payload exited with status ',
        3124: f'Failed to connect to {endpoint_url} for projects["{project}"].delete payload',
        3125: f'Failed to run projects["{project}"].delete payload on {endpoint_url}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get instances client obj
        ret = project_rcc.run(cli='instances.get', name=instance_name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            # Instance not found - already removed from host
            return True, '', fmt.successful_payloads

        # Stop the instance.
        instance = ret['payload_message']
        state = instance.state()
        if state.status == 'Running':
            instance.stop(force=False, wait=True)

        instance.delete(wait=True)

        # Check if it is the last instance in the project
        ret = project_rcc.run(cli=f'instances.all')
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+3}: {messages[prefix+3]}"), fmt.successful_payloads

        if len(ret['payload_message']) == 0:
            # It was the last LXD instance in the project on this LXD host so the project can be deleted.
            ret = rcc.run(cli=f'projects["{project}"].delete', api=True)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
            if ret["payload_code"] != API_SUCCESS:
                return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3120, {})
    if status is False:
        return status, msg

    return True, f'1100: {messages[1100]}'

