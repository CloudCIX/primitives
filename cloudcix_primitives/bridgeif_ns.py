#stdlib
import ipaddress
import json
from pathlib import Path
from typing import Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh, CONNECTION_ERROR, VALIDATION_ERROR
# local
from cloudcix_primitives.utils import load_pod_config, PodnetErrorFormatter, SSHCommsWrapper


__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0


def build(
    bridgename: str,
    namespace: str,
    config_file=None
) -> Tuple[bool, str]:
    """
    description:
        Creates a veth link on the main namespace and connects it to a bridge.
        Then, it moves one end of the link to a VRF network namespace and sets the interface up.

    parameters:
        bridgename:
            description: The name of the bridge on the main namespace.
            type: string
            required: true
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag indicating if the veth link creation was successful,
            and the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'1000: Successfully created interface {namespace}.{bridgename} inside namespace {namespace}',

        3021: f'3021: Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_check:  ',
        3022: f'3022: Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_add:  ',
        3023: f'3023: Failed to run interface_add payload on the enabled PodNet. Payload exited with status ',
        3024: f'3024: Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_main:  ',
        3025: f'3025: Failed to run interface_main payload on the enabled PodNet. Payload exited with status ',
        3026: f'3026: Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_ns:  ',
        3027: f'3027: Failed to run interface_ns payload on the enabled PodNet. Payload exited with status ',
        3028: f'3028: Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_up:  ',
        3029: f'3029: Failed to run interface_up payload on the enabled PodNet. Payload exited with status ',

        3051: f'3051: Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_check:  ',
        3052: f'3052: Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_add:  ',
        3053: f'3053: Failed to run interface_add payload on the disabled PodNet. Payload exited with status ',
        3054: f'3054: Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_main:  ',
        3055: f'3055: Failed to run interface_main payload on the disabled PodNet. Payload exited with status ',
        3056: f'3056: Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_ns:  ',
        3057: f'3057: Failed to run interface_ns payload on the disabled PodNet. Payload exited with status ',
        3058: f'3058: Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_up:  ',
        3059: f'3059: Failed to run interface_up payload on the disabled PodNet. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    status, config_data, msg = load_pod_config(config_file)
    if not status:
        if config_data['raw'] is None:
            return False, msg
        else:
            return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
                                                                               indent=2,
                                                                               sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'interface_check' : f'ip netns exec {namespace} ip link show {namespace}.{bridgename}',
            'interface_add' : f'ip link add {bridgename}.{namespace} type veth peer name {namespace}.{bridgename}',
            'interface_main' : f'ip link set dev {bridgename}.{namespace} master {bridgename}',
            'interface_ns': f'ip link set dev {namespace}.{bridgename} netns {namespace}',
            'interface_up' : f'ip netns exec {namespace} ip link set dev {namespace}.{bridgename} up',
        }

        ret = rcc.run(payloads['interface_check'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        add_interface = True
        if ret["payload_code"] == SUCCESS_CODE:
            # No need to add this bidge space to the namespace if it exists already
            add_interface = False
        fmt.add_successful('interface_check', ret)

        if add_interface:
            # If the interface does not already exists then create and prepare the interface then activate it.
            ret = rcc.run(payloads['interface_add'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            fmt.add_successful('interface_add', ret)

            ret = rcc.run(payloads['interface_main'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            fmt.add_successful('interface_main', ret)

            ret = rcc.run(payloads['interface_ns'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            fmt.add_successful('interface_ns', ret)

        ret = rcc.run(payloads['interface_up'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+9}: " + messages[prefix+9]), fmt.successful_payloads
        fmt.add_successful('interface_up', ret)

        return True, "", fmt.successful_payloads


    status, msg, successful_payloads = run_podnet(enabled,3020,{})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000] + '\n' + msg


def read(
    bridgename: str,
    namespace: str,
    config_file=None
) -> Tuple[bool, dict, str]:
    """
    description:
        reads a namespace.bridgename interface from namespace.

    parameters:
        bridgename:
            description: The name of the bridge associated with the interface.
            type: string
            required: true
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag indicating if the interface was successfully read,
            and the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1200: f'1200: Successfully read interface {namespace}.{bridgename} inside namespace {namespace}',
        1201: f'1201: Interface {namespace}.{bridgename} does not exist',

        3221: f'3221: Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_check:  ',
        3222: f'3222: Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_del:  ',
        3223: f'3223: Failed to run interface_del payload on the enabled PodNet. Payload exited with status ',

        3251: f'3251: Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_check:  ',
        3252: f'3252: Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_del:  ',
        3253: f'3253: Failed to run interface_del payload on the disabled PodNet. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    status, config_data, msg = load_pod_config(config_file)
    if not status:
        if config_data['raw'] is None:
            return False, None, msg
        else:
            return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],indent=2,sort_keys=True)

    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']


    name_grepsafe = f"{namespace}.{bridgename}".replace('.', '\.')

    # Define payload

    def run_podnet(podnet_node, prefix, successful_payloads, data_dict):
        retval = True
        data_dict[podnet_node] = {}

        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'interface_show': f'ip netns exec {namespace} ip link show | grep --word "{name_grepsafe}"'
        }

        ret = rcc.run(payloads['interface_show'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1} : " + messages[prefix+1])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2} : " + messages[prefix+2])
        else:
            data_dict[podnet_node]['entry'] = ret["payload_message"].strip()
            fmt.add_successful('interface_show', ret)

        return retval, fmt.message_list, fmt.successful_payloads, data_dict

    retval_a, msg_list, successful_payloads, data_dict = run_podnet(enabled, 3220, {}, {})

    retval_b, msg_list, successful_payloads, data_dict = run_podnet(disabled, 3250, successful_payloads, data_dict)

    if not (retval_a and retval_b):
        return (retval_a and retval_b), data_dict, msg_list
    else:
        return True, data_dict, (messages[1200])



def scrub(
    bridgename: str,
    namespace: str,
    config_file=None
) -> Tuple[bool, str]:
    """
    description:
        Removes the specified veth interface from the given namespace.

    parameters:
        bridgename:
            description: The name of the bridge associated with the interface.
            type: string
            required: true
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag indicating if the interface was successfully deleted,
            and the output or error message.
        type: tuple
    """

    # Define message
    messages = {
        1100: f'1100: Successfully removed interface {namespace}.{bridgename} inside namespace {namespace}',
        1101: f'1101: Interface {namespace}.{bridgename} does not exist',

        3121: f'3121: Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_check:  ',
        3122: f'3122: Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_del:  ',
        3123: f'3123: Failed to run interface_del payload on the enabled PodNet. Payload exited with status ',

        3151: f'3151: Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_check:  ',
        3152: f'3152: Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_del:  ',
        3153: f'3153: Failed to run interface_del payload on the disabled PodNet. Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    status, config_data, msg = load_pod_config(config_file)
    if not status:
        if config_data['raw'] is None:
            return False, msg
        else:
            return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
                                                                               indent=2,
                                                                               sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'stdout', 'payload_error': 'stderr'},
            successful_payloads
        )

        payloads = {
            'interface_check': f'sudo ip netns exec {namespace} ip link show dev {namespace}.{bridgename}',
            'interface_del':  f'sudo ip netns exec {namespace} ip link del {namespace}.{bridgename}'
        }

        interface_exists = True

        ret = rcc.run(payloads['interface_check'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            #If the interface already does NOT exists returns info and true state
            interface_exists = False
        fmt.add_successful('interface_check', ret)

        if not interface_exists:
            return True, fmt.payload_error(ret, f"1101: " + messages[1101]), fmt.successful_payloads

        ret = rcc.run(payloads['interface_del'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        fmt.add_successful('interface_del', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3150, successful_payloads)
    if status == False:
        return status, msg

    return status, messages[1100] + '\n' + msg
