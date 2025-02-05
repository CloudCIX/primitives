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

        3021: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_check_inside: ',
        3022: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_check_outside: ',
        3023: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload stale_outside_interface_del: ',
        3024: f'Failed to run stale_outside_interface_del payload on the enabled PodNet. Payload exited with status ',
        3025: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload stale_inside_interface_del: ',
        3026: f'Failed to run stale_inside_interface_del payload on the enabled PodNet. Payload exited with status ',
        3027: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_add:  ',
        3028: f'Failed to run interface_add payload on the enabled PodNet. Payload exited with status ',
        3029: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_main:  ',
        3030: f'Failed to run interface_main payload on the enabled PodNet. Payload exited with status ',
        3031: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_ns:  ',
        3032: f'Failed to run interface_ns payload on the enabled PodNet. Payload exited with status ',
        3033: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_up:  ',
        3034: f'Failed to run interface_up payload on the enabled PodNet. Payload exited with status ',

        3051: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_check_inside: ',
        3052: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_check_inside: ',
        3053: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload stale_outside_interface_del: ',
        3054: f'Failed to run stale_outside_interface_del payload on the disabled PodNet. Payload exited with status ',
        3055: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload stale_inside_interface_del: ',
        3056: f'Failed to run stale_inside_interface_del payload on the disabled PodNet. Payload exited with status ',
        3057: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_add:  ',
        3058: f'Failed to run interface_add payload on the disabled PodNet. Payload exited with status ',
        3059: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_main:  ',
        3060: f'Failed to run interface_main payload on the disabled PodNet. Payload exited with status ',
        3061: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_ns:  ',
        3062: f'Failed to run interface_ns payload on the disabled PodNet. Payload exited with status ',
        3063: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload interface_up:  ',
        3064: f'Failed to run interface_up payload on the disabled PodNet. Payload exited with status ',
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
            'interface_check_outside' : f'ip link show {bridgename}.{namespace}',
            'interface_check_inside' : f'ip netns exec {namespace} ip link show {namespace}.{bridgename}',
            'stale_outside_interface_del':  f'ip link del {bridgename}.{namespace}',
            'stale_inside_interface_del':  f'ip netns exec {namespace} ip link del {namespace}.{bridgename}',
            'interface_add' : f'ip link add {bridgename}.{namespace} type veth peer name {namespace}.{bridgename}',
            'interface_main' : f'ip link set dev {bridgename}.{namespace} master {bridgename}',
            'interface_ns': f'ip link set dev {namespace}.{bridgename} netns {namespace}',
            'interface_up' : f'ip netns exec {namespace} ip link set dev {namespace}.{bridgename} up',
        }

        interface_present_inside = False
        interface_present_outside = False
        add_interface=False

        ret = rcc.run(payloads['interface_check_outside'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] == SUCCESS_CODE:
            interface_present_outside = True
        fmt.add_successful('interface_check_outside', ret)

        ret = rcc.run(payloads['interface_check_inside'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if ret["payload_code"] == SUCCESS_CODE:
            interface_present_inside = True
        fmt.add_successful('interface_check_inside', ret)

        # This happens when there is a stale interface left over from a
        # scrubbed and rebuilt name space. We need to remove it because it is
        # not connected to anything and its presence will cause later payloads
        # to fail.
        if interface_present_outside and (not interface_present_inside):
            ret = rcc.run(payloads['stale_outside_interface_del'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
            fmt.add_successful('stale_outside_interface_del', ret)

        # This shouldn't happen but in case it does (e.g. through somebody
        # manually deleting the outside interface with the name space still
        # around), make sure it won't pose a problem either.
        if (not interface_present_outside) and interface_present_inside:
            ret = rcc.run(payloads['stale_inside_interface_del'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
            fmt.add_successful('stale_inside_interface_del', ret)

        if not ( interface_present_inside and interface_present_outside ):
            add_interface = True

        if add_interface:
            # If the interface does not already exists then create and prepare the interface then activate it.
            ret = rcc.run(payloads['interface_add'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
            fmt.add_successful('interface_add', ret)

            ret = rcc.run(payloads['interface_main'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+9}: " + messages[prefix+9]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+10}: " + messages[prefix+10]), fmt.successful_payloads
            fmt.add_successful('interface_main', ret)

            ret = rcc.run(payloads['interface_ns'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+11}: " + messages[prefix+11]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+12}: " + messages[prefix+12]), fmt.successful_payloads
            fmt.add_successful('interface_ns', ret)

        ret = rcc.run(payloads['interface_up'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+13}: " + messages[prefix+13]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+14}: " + messages[prefix+14]), fmt.successful_payloads
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
        1200: f'Successfully read interface {namespace}.{bridgename} inside namespace {namespace}',
        1201: f'Interface {namespace}.{bridgename} does not exist',

        3221: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload inside_interface_show: ',
        3222: f'Failed to run inside_interface_show payload on the enabled PodNet. Payload exited with status ',
        3223: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload outside_interface_show: ',
        3224: f'Failed to run outside_interface_show payload on the enabled PodNet. Payload exited with status ',

        3251: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload inside_interface_show: ',
        3252: f'Failed to run inside_interface_show payload on the disabled PodNet. Payload exited with status ',
        3253: f'Failed to connect to the disabled PodNet from the config file {config_file} for payload outside_interface_show: ',
        3254: f'Failed to run outside_interface_show payload on the disabled PodNet. Payload exited with status ',

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
            'inside_interface_show' : f'ip link show {bridgename}.{namespace}',
            'outside_interface_show' : f'ip netns exec {namespace} ip link show {namespace}.{bridgename}',
        }

        ret = rcc.run(payloads['inside_interface_show'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+1} : " + messages[prefix+1])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+2} : " + messages[prefix+2])
        else:
            data_dict[podnet_node]['entry'] = ret["payload_message"].strip()
            fmt.add_successful('inside_interface_show', ret)

        ret = rcc.run(payloads['outside_interface_show'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            retval = False
            fmt.store_channel_error(ret, f"{prefix+3} : " + messages[prefix+3])
        if ret["payload_code"] != SUCCESS_CODE:
            retval = False
            fmt.store_payload_error(ret, f"{prefix+4} : " + messages[prefix+4])
        else:
            data_dict[podnet_node]['entry'] = ret["payload_message"].strip()
            fmt.add_successful('outside_interface_show', ret)

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
        1100: f'1100: Successfully removed interface {namespace}.{bridgename} inside namespace {namespace} on both PodNet nodes.',
        1121: f'Interface {namespace}.{bridgename} does not exist on enabled PodNet: interface_check payload exited with status ',
        1151: f'Interface {namespace}.{bridgename} does not exist on disabled PodNet: interface_check payload exited with status ',

        3121: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_check_inside: ',
        3122: f'Failed to run payload interface_check_inside on the enabled PodNet. Payload exited with status ',
        3123: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_check_outside: ',
        3124: f'Failed to run payload interface_check_outside on the enabled PodNet. Payload exited with status ',
        3125: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload stale_inside_interface_del:  ',
        3126: f'Failed to run payload stale_inside_interface_del on the enabled PodNet. Payload exited with status ',
        3127: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload stale_outside_interface_del:  ',
        3128: f'Failed to run payload stale_outside_interface_del on the enabled PodNet. Payload exited with status ',

        3121: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_check_inside: ',
        3122: f'Failed to run payload interface_check_inside on the enabled PodNet. Payload exited with status ',
        3123: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload interface_check_outside: ',
        3124: f'Failed to run payload interface_check_outside on the enabled PodNet. Payload exited with status ',
        3125: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload stale_inside_interface_del:  ',
        3126: f'Failed to run payload stale_inside_interface_del on the enabled PodNet. Payload exited with status ',
        3127: f'Failed to connect to the enabled PodNet from the config file {config_file} for payload stale_outside_interface_del:  ',
        3128: f'Failed to run payload stale_outside_interface_del on the enabled PodNet. Payload exited with status ',
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
            'interface_check_outside' : f'ip link show {bridgename}.{namespace}',
            'interface_check_inside' : f'ip netns exec {namespace} ip link show {namespace}.{bridgename}',
            'inside_interface_del':  f'ip netns exec {namespace} ip link del {namespace}.{bridgename}',
            'outside_interface_del':  f'ip link del {bridgename}.{namespace}',
        }

        interface_present_inside = True
        interface_present_outside = True

        ret = rcc.run(payloads['interface_check_inside'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            if ret["payload_code"] >= 2:
                fmt.store_payload_error(ret, f"{prefix+2} : " + messages[prefix+2])
            # If the interface already does NOT exists returns info and true state
            if ret["payload_code"] == 1:
                interface_present_outside = False
        fmt.add_successful('interface_check_inside', ret)

        ret = rcc.run(payloads['interface_check_outside'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            if ret["payload_code"] >= 2:
                fmt.store_payload_error(ret, f"{prefix+4} : " + messages[prefix+4])
            # If the interface already does NOT exists returns info and true state
            if ret["payload_code"] == 1:
                interface_present_inside = False
        fmt.add_successful('interface_check_outside', ret)

        if (not interface_present_inside) and (not interface_present_outside):
            return True, fmt.payload_error(ret, f"{prefix+1-2000}: " + messages[prefix+1-2000]), fmt.successful_payloads

        if interface_present_inside:
            ret = rcc.run(payloads['inside_interface_del'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
            fmt.add_successful('inside_interface_del', ret)

        if interface_present_outside:
            ret = rcc.run(payloads['outside_interface_del'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
            fmt.add_successful('outside_interface_del', ret)

        return True, "", fmt.successful_payloads

    status, msg_enabled, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg_enabled

    status, msg_disabled, successful_payloads = run_podnet(disabled, 3150, successful_payloads)
    if status == False:
        return status, msg_disabled

    return status, messages[1100] + '\n' + msg_enabled + msg_disabled
