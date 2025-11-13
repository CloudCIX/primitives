"""
Primitive for managing LXD Projects.
"""
# stdlib
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
        name: str,
        host: str,
        verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    description:
        Create an LXD project on the LXD host.

    parameters:
        name:
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        host:
            description: The endpoint URL for the LXD Host where the project will be created.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false

    return:
        description: |
            A tuple with a boolean flag indicating success or failure and a message.
        type: tuple
    """
    # Define messages
    messages = {
        1000: f'Successfully created project {name} on {host}',
        1001: f'Project {name} already exists on {host}',
        3021: f'Failed to connect to {host} for projects.exists payload',
        3022: f'Failed to run projects.exists payload on {host}. Payload exited with status ',
        3023: f'Failed to connect to {host} for projects.create payload',
        3024: f'Failed to create project {name} on {host}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Check if project already exists
        ret = rcc.run(cli='projects.exists', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        project_exists = ret['payload_message']
        fmt.add_successful('projects.exists', ret)

        if project_exists:
            return True, f'1001: {messages[1001]}', fmt.successful_payloads

        # Create the project
        ret = rcc.run(cli='projects.create', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: {messages[prefix+3]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+4}: {messages[prefix+4]}"), fmt.successful_payloads

        fmt.add_successful('projects.create', ret)

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3020, {})

    if status is False:
        return status, msg

    return True, f'1000: {messages[1000]}'


def read(
        name: str,
        host: str,
        verify_lxd_certs: bool = True,
) -> Tuple[bool, dict, str]:
    """
    description:
        Read an LXD project configuration from the LXD host.

    parameters:
        name:
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        host:
            description: The endpoint URL for the LXD Host.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false

    return:
        description: |
            A tuple with a boolean flag indicating success or failure, project data, and a message.
        type: tuple
    """
    # Define messages
    messages = {
        1200: f'Successfully read project {name} from {host}',
        3221: f'Failed to connect to {host} for projects.get payload',
        3222: f'Failed to run projects.get payload on {host}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        result = {}

        # Get the project
        ret = rcc.run(cli='projects.get', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads, result
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads, result

        project = ret['payload_message']
        fmt.add_successful('projects.get', ret)

        # Extract project data
        result['name'] = project.name
        if hasattr(project, 'config'):
            result['config'] = project.config
        if hasattr(project, 'description'):
            result['description'] = project.description

        return True, '', fmt.successful_payloads, result

    status, msg, successful_payloads, result = run_host(host, 3220, {})

    if not status:
        return False, {}, msg

    data = {host: result}
    return True, data, f'1200: {messages[1200]}'


def scrub(
        name: str,
        host: str,
        verify_lxd_certs: bool = True,
) -> Tuple[bool, str]:
    """
    description:
        Delete an LXD project from the LXD host.

    parameters:
        name:
            description: Unique identification name of the LXD Project on the LXD Host.
            type: string
            required: true
        host:
            description: The endpoint URL for the LXD Host where the project will be deleted.
            type: string
            required: true
        verify_lxd_certs:
            description: Boolean to verify LXD certs.
            type: boolean
            required: false

    return:
        description: |
            A tuple with a boolean flag indicating success or failure and a message.
        type: tuple
    """
    # Define messages
    messages = {
        1100: f'Successfully scrubbed project {name} from {host}',
        3121: f'Failed to connect to {host} for projects.get payload',
        3122: f'Failed to run projects.get payload on {host}. Payload exited with status ',
        3123: f'Failed to delete project {name}. Error: ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):
        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        # Get the project
        ret = rcc.run(cli='projects.get', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: {messages[prefix+1]}"), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: {messages[prefix+2]}"), fmt.successful_payloads

        project = ret['payload_message']
        fmt.add_successful('projects.get', ret)

        # Delete the project
        try:
            project.delete()
            fmt.add_successful('projects.delete', {'name': name})
        except Exception as e:
            return False, f"{prefix+3}: {messages[prefix+3]}{e}", fmt.successful_payloads

        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(host, 3120, {})

    if status is False:
        return status, msg

    return True, f'1100: {messages[1100]}'