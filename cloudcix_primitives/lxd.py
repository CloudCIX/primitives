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
        Configures a LXD instance on the LXD host.

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
        3011: f'Invalid instance_type "{instance_type}" sent. Suuported instance types are "containers" and "virtual_machines"',
        3021: f'Failed to connect to {endpoint_url} for projects.exists payload',
        3022: f'Failed to run projects.exists payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to connect to {endpoint_url} for projects.create payload',
        3024: f'Failed to run projects.create payload on {endpoint_url}. Payload exited with status ',
        3025: f'Failed to connect to {endpoint_url} for {instance_type}.exists payload',
        3026: f'Failed to run {instance_type}.exists payload on {endpoint_url}. Payload exited with status ',
        3027: f'Failed to connect to {endpoint_url} for {instance_type}.exists payload',
        3028: f'Failed to run {instance_type}.exists payload on {endpoint_url}. Payload exited with status ',
    }

    # validation
    if instance_type not in SUPPORTED_INSTANCES:
        return False, f'3011: {messages[3011]}'

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
            instance = ret['payload_message']
            instance.start(wait=True)
        
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'


def quiesce(endpoint_url: str, project: str, name: str, instance_type: str, verify_lxd_certs=True) -> Tuple[bool, str]:
    """
    description: Shutdown the LXD Instance

    parameters:

    return:
        description: |
            A tuple with a boolean flag stating the quiesce was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1400: f'Successfully quiesced {instance_type} {name} on {endpoint_url}',
        3411: f'Invalid instance_type "{instance_type}" sent. Suuported instance types are "containers" and "virtual_machines"',

        3421: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3422: f'Failed to run {instance_type}.get payload on {endpoint_url}. Payload exited with status ',
        3423: f'Failed to quiesce {instance_type} on {endpoint_url}. Instance was found in an uxecpected state of ',
    }

    # validation
    if instance_type not in SUPPORTED_INSTANCES:
        return False, f'3411: {messages[3411]}'

    def run_host(endpoint_url, prefix, successful_payloads):

        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get instances client obj
        ret = project_rcc.run(cli=f'{instance_type}.get', name=name)
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


def restart(endpoint_url: str, project: str, name: str, instance_type: str, verify_lxd_certs=True) -> Tuple[bool, str]:
    """
    description: Restart the LXD Instance

    parameters:

    return:
        description: |
            A tuple with a boolean flag stating the restart was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1500: f'Successfully restarted {instance_type} {name} on {endpoint_url}',
        3511: f'Invalid instance_type "{instance_type}" sent. Suuported instance types are "containers" and "virtual_machines"',

        3521: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3522: f'Failed to run {instance_type}.get payload on {endpoint_url}. Payload exited with status ',
        3523: f'Failed to restart {instance_type} on {endpoint_url}. Instance was found in an uxecpected state of ',
    }

    # validation
    if instance_type not in SUPPORTED_INSTANCES:
        return False, f'3511: {messages[3511]}'

    def run_host(endpoint_url, prefix, successful_payloads):

        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get instances client obj
        ret = project_rcc.run(cli=f'{instance_type}.get', name=name)
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


def read(endpoint_url: str, project: str, name: str, instance_type: str, verify_lxd_certs=True) -> Tuple[bool, str]:
    """
    description:
        Reads a instance on the LXD host.

    parameters:
        endpoint_url:
            description: The endpoint URL for the LXD Host where the service will be read
            type: string
            required: true
        name:
            description: The name of the instance to read
            type: integer
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
        1200: f'Successfully read {instance_type} {name} on {endpoint_url}.',
        3211: f'Invalid instance_type "{instance_type}" sent. Suuported instance types are "containers" and "virtual_machines"',

        3221: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3222: f'Failed to run {instance_type}.get payload on {endpoint_url}. Payload exited with status ',
    }

    # validation
    if instance_type not in SUPPORTED_INSTANCES:
        return False, f'3211: {messages[3211]}'

    def run_host(endpoint_url, prefix, successful_payloads, data_dict):
        retval = True
        data_dict[endpoint_url] = {}

        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )
        ret = project_rcc.run(cli=f'{instance_type}["{name}"].get', api=True)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1}: " + messages[prefix+1])
        elif ret["payload_code"] != API_SUCCESS:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2}: " + messages[prefix+2])
        else:
            data_dict[endpoint_url][f'{instance_type}["{name}"].get'] = ret["payload_message"].json()
            fmt.add_successful(f'{instance_type}["{name}"].get', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(endpoint_url, 3220, {}, {})
    message_list = list()
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
        return True, data_dict, f'1200: {messages[1200]}'


def scrub(endpoint_url: str, project: str, name: str, instance_type: str, verify_lxd_certs=True) -> Tuple[bool, str]:
    """
    description: Scrub the LXD Instance

    parameters:

    return:
        description: |
            A tuple with a boolean flag stating the scrub was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1100: f'Successfully scruubbed {instance_type} {name} on {endpoint_url}',
        3111: f'Invalid instance_type "{instance_type}" sent. Suuported instance types are "containers" and "virtual_machines"',

        3121: f'Failed to connect to {endpoint_url} for {instance_type}.get payload',
        3122: f'Failed to run {instance_type}.get payload on {endpoint_url}. Payload exited with status ',
        3123: f'Failed to connect to {endpoint_url} for instances.all payload',
        3124: f'Failed to run instances.all payload on {endpoint_url}. Payload exited with status ',
        3125: f'Failed to connect to {endpoint_url} for projects["{project}"].delete payload',
        3126: f'Failed to run projects["{project}"].delete payload on {endpoint_url}. Payload exited with status ',
    }

    # validation
    if instance_type not in SUPPORTED_INSTANCES:
        return False, f'3411: {messages[3111]}'

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        project_rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs, project)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get instances client obj
        ret = project_rcc.run(cli=f'{instance_type}.get', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        # Stop the instance.
        instance = ret['payload_message']
        state = instance.state()
        if state.status == 'Running':
            instance.stop(force=False, wait=True)

        instance.delete(wait=True)

        # Check if it is the last instance in the project
        ret = project_rcc.run(cli=f'instances.all')
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: {messages[prefix+3]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+4}: {messages[prefix+4]}"), fmt.successful_payloads

        if len(ret['payload_message']) == 0:
            # It was the last LXD instance in the project on this LXD host so the project can be deleted.
            ret = rcc.run(cli=f'projects["{project}"].delete', api=True)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            if ret["payload_code"] != API_SUCCESS:
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3120, {})
    if status is False:
        return status, msg

    return True, f'1100: {messages[1100]}'
