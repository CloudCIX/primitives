"""
Primitive for Private Bridge in LXD
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
    endpoint_url: str,
    name: int,
    config=None,
    verify_lxd_certs=True,
) -> Tuple[bool, str]:
    """
    description:
        Configures a bridge on the LXD host.

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
        
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1000: f'Successfully created bridge_lxd {name} on {endpoint_url}.',

        3021: f'Failed to connect to {endpoint_url} for networks.exists payload',
        3022: f'Failed to run networks.exists payload on {endpoint_url}. Payload exited with status ',
        3023: f'Failed to connect to {endpoint_url} for networks.create payload',
        3024: f'Failed to run networks.create payload on {endpoint_url}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads):

        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        ret = rcc.run(cli='networks.exists', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads

        bridge_exists = ret['payload_message']
        fmt.add_successful('networks.exists', ret)

        if bridge_exists == False:
            ret = rcc.run(cli='networks.create', name=name, type='bridge', config=config)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            if ret["payload_code"] != API_SUCCESS:
                return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3020, {})
    if status is False:
        return status, msg

    return True, messages[1000]


def read(endpoint_url: str,
    name: int,
    verify_lxd_certs=True,
) -> Tuple[bool, str]:
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
            A tuple with a boolean flag stating if the read was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1200: f'Successfully read bridge_lxd {name} on {endpoint_url}.',

        3221: f'Failed to connect to {endpoint_url} for networks.get payload',
        3222: f'Failed to run networks.get payload on {endpoint_url}. Payload exited with status ',
    }

    def run_host(endpoint_url, prefix, successful_payloads, data_dict):
        retval = True
        data_dict[endpoint_url] = {}

        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        ret = rcc.run(cli='networks.get', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1}: " + messages[prefix+1])
        elif ret["payload_code"] != API_SUCCESS:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2}: " + messages[prefix+2])
        else:
            data_dict[endpoint_url]['networks.get'] = ret["payload_message"]
            fmt.add_successful('networks.get', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval, msg_list, successful_payloads, data_dict = run_host(endpoint_url, 3220, {}, {})
    message_list = list()
    message_list.extend(msg_list)

    if not retval:
        return retval, data_dict, message_list
    else:
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

    def run_host(endpoint_url, prefix, successful_payloads):

        rcc = LXDCommsWrapper(comms_lxd, endpoint_url, verify_lxd_certs)
        fmt = HostErrorFormatter(
            endpoint_url,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads,
        )

        ret = rcc.run(cli='networks.exists', name=name)
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != API_SUCCESS:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads

        bridge_exists = ret['payload_message']
        fmt.add_successful('networks.exists', ret)

        if bridge_exists == True:
            ret = rcc.run(cli=f'networks["{name}"].delete', api=True)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            if ret["payload_code"] != API_SUCCESS:
                return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        
        return True, '', fmt.successful_payloads

    status, msg, successful_payloads = run_host(endpoint_url, 3120, {})
    if status is False:
        return status, msg

    return True, messages[1100]
