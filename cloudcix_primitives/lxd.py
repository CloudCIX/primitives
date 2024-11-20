"""
Primitive for managing an LXD instance.
"""
# stdlib
from typing import Tuple
# libs
from cloudcix.rcc import API_SUCCESS, comms_lxd, CHANNEL_SUCCESS
# local
from cloudcix_primitives.utils import HostErrorFormatter, LXDCommsWrapper


__all__ = [
    'build',
    'read',
    'scrub',
]


SUPPORTED_INSTANCES = ['virtual_machines', 'containers']


def build(
    endpoint_url: str,
    project: str,
    name: str,
    instance_type: str,
    image: dict,
    cpu: int,
    gateway_interface: dict,
    ram: int,
    size: int,
    network_config: str,
    userdata: str,
    secondary_interfaces=[],
    verify_lxd_certs=True,
) -> Tuple[bool, str]:
    """
    description:
        Configures a bridge on the LXD host.

    parameters:
        
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1000: f'Successfully created {instance_type} {name} on {endpoint_url}',
        # validations
        3011: f'Invalid instance_type "{instance_type}" sent. Suuported instance types are "container" and "virtual_machine"',

        3021: f'Failed to connect to {endpoint_url} for projects.exists payload',
        3022: f'Failed to run projects.exists payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to connect to {endpoint_url} for projects.create payload',
        3024: f'Failed to run projects.create payload on {endpoint_url}. Payload exited with status ',
        3025: f'Failed to connect to {endpoint_url} for {instance_type}.exists payload',
        3026: f'Failed to run {instance_type}.exists payload on {endpoint_url}. Payload exited with status ',
        3027: f'Failed to connect to {endpoint_url} for {instance_type}.exists payload',
        3028: f'Failed to run {instance_type}.exists payload on {endpoint_url}. Payload exited with status ',
        3029: f'Failed to connect to {endpoint_url} for {instance_type}["{name}"].start payload',
        3030: f'Failed to run {instance_type}["{name}"].start payload on {endpoint_url}. Payload exited with status ',
    }

    # validation
    messages_list = []
    def validate_instance_type(instance_type, msg_index):
        if instance_type not in SUPPORTED_INSTANCES:
            messages_list.append(f'{messages[msg_index + 1]}: {messages[msg_index + 1]}')
            return False

    validated = validate_instance_type(instance_type, 3010)

    if validated is False:
        return False, '; '.join(messages_list)

    config = {
        'name': name,
        'architecture': 'x86_64',
        'profiles': ['default'],
        'ephemeral': False,
        'config': {
            'limits.cpu': f'{cpu}',
            'limits.memory': f'{ram}GB',
            'volatile.eth0.hwaddr': gateway_interface['mac_address'],
            'cloud-init.network-config': network_config,
            'cloud-init.user-data': userdata,
        },
        'devices': {
            'root': {
                'type': 'disk',
                'path': '/',
                'pool': 'default',
                'size': f'{size}GB',
            },
            'eth0': {
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
    if len(secondary_interfaces) > 0:
        n = 1
        for interface in secondary_interfaces:
            config['devices'][f'eth{n}'] = {
                'type': 'nic',
                'network': f'br{interface["vlan"]}',
                'ipv4.address': None,
                'ipv6.address': None,
            }
            config['config'][f'volatile.eth{n}.hwaddr'] = interface['mac_address']
            n += 1

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
        ret = project_rcc.run(cli=f'{instance_type}.exists', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads

        instance_exists = ret['payload_message']
        fmt.add_successful(f'{instance_type}.exists', ret)

        if instance_exists == False:
            # Build instance in Project
            ret = project_rcc.run(cli=f'{instance_type}.create', config=config, wait=True)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            if ret["payload_code"] != API_SUCCESS:
                return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads

            # Start the instance.
            ret = project_rcc.run(cli=f'{instance_type}["{name}"].start', api=True, wait=True)
            # instance = ret['payload_message']
            # instance.start(wait=True)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+9}: " + messages[prefix+9]), fmt.successful_payloads
            if ret["payload_code"] != API_SUCCESS:
                return False, fmt.payload_error(ret, f"{prefix+10}: " + messages[prefix+10]), fmt.successful_payloads
        
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]

