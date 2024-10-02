# stdlib
import json
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS
from cloudcix_primitives.utils import load_pod_config, SSHCommsWrapper, PodnetErrorFormatter
# local


__all__ = [
    'build',
    'scrub',
]

SUCCESS_CODE = 0


def build(
    vlan: int,
    ifname: str,
    namespace: str,
    config_file=None
) -> Tuple[bool, str]:
    """
    description:
        Creates a vlan tagged interface. The it moves the interface to the namespace and bring it up

    parameters:
        vlan:
            description: VLAN id assigned to the interface.
            type: integer
            required: true
        ifname:
            description: Interface name.
            type: string
            required: true
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag indicating if the VLAN tagged interface creation was successful,
            and the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'Successfully created interface {ifname}.{vlan} inside namespace {namespace} ',
        1001: f'Interface {ifname}.{vlan} already exists inside namespace {namespace} ',

        3021: f'Failed to connect to the enabled PodNet for vlanif_check payload:  ',
        3022: f'Failed to connect to the enabled PodNet for vlanif_add payload:  ',
        3023: f'Failed to run vlanif_add payload on the enabled PodNet. Payload exited with status ',
        3024: f'Failed to connect to the enabled PodNet for vlanif_ns payload:  ',
        3025: f'Failed to run vlanif_ns payload on the enabled PodNet. Payload exited with status ',
        3026: f'Failed to connect to the enabled PodNet for vlanif_up payload:  ',
        3027: f'Failed to run vlanif_up payload on the enabled PodNet. Payload exited with status ',

        3051: f'Failed to connect to the disabled PodNet for vlanif_check payload:  ',
        3052: f'Failed to connect to the disabled PodNet for vlanif_add payload:  ',
        3053: f'Failed to run vlanif_add payload on the disabled PodNet. Payload exited with status ',
        3054: f'Failed to connect to the disabled PodNet for vlanif_ns payload:  ',
        3055: f'Failed to run vlanif_ns payload on the disabled PodNet. Payload exited with status ',
        3056: f'Failed to connect to the disabled PodNet for vlanif_up payload:  ',
        3057: f'Failed to run vlanif_up payload on the disabled PodNet. Payload exited with status ',
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
            'vlanif_check' : f'ip netns exec {namespace} ip link show {ifname}.{vlan}',
            'vlanif_add' : f'ip link add link {ifname} name {ifname}.{vlan} type vlan id {vlan}',
            'vlanif_ns': f'ip link set dev {ifname}.{vlan} netns {namespace}',
            'vlanif_up' : f'ip netns exec {namespace} ip link set dev {ifname}.{vlan} up',
        }

        ret = rcc.run(payloads['vlanif_check'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        create_vlanif = True
        if ret["payload_code"] == SUCCESS_CODE:
            #If the interface already exists returns info and true state
            create_vlanif = False
            fmt.payload_error(ret, f"1001: " + messages[1001]), fmt.successful_payloads
        fmt.add_successful('vlanif_check', ret)

        #STEP 1-4

        if create_vlanif:
           ret = rcc.run(payloads['vlanif_add'])
           if ret["channel_code"] != CHANNEL_SUCCESS:
               return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
           if ret["payload_code"] != SUCCESS_CODE:
               return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
           fmt.add_successful('vlanif_add', ret)

           ret = rcc.run(payloads['vlanif_ns'])
           if ret["channel_code"] != CHANNEL_SUCCESS:
               return False, fmt.channel_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
           if ret["payload_code"] != SUCCESS_CODE:
               return False, fmt.payload_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
           fmt.add_successful('vlanif_ns', ret)

        ret = rcc.run(payloads['vlanif_up'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
        fmt.add_successful('vlanif_up', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled,3020,{})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]

def scrub(
    vlan: int,
    ifname: str,
    namespace: str,
    config_file=None
) -> Tuple[bool, str]:
    """
    description:
        Creates a vlan tagged interface. The it moves the interface to the namespace and bring it up

    parameters:
        vlan:
            description: VLAN id assigned to the interface.
            type: integer
            required: true
        ifname:
            description: Interface name.
            type: string
            required: true
        namespace:
            description: The VRF network namespace identifier, such as 'VRF123'.
            type: string
            required: true

    return:
        description: |
            A tuple with a boolean flag indicating if the VLAN tagged interface deletion was successful,
            and the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1100: f'Successfully removed vlanif {ifname}.{vlan} inside namespace {namespace} ',
        1101: f'vlanif {ifname}.{vlan} does not exist ',

        3121: f'Failed to connect to the enabled PodNet for vlanif_check payload:  ',
        3122: f'Failed to connect to the enabled PodNet for vlanif_del payload:  ',
        3123: f'Failed to run vlanif_del payload on the enabled PodNet. Payload exited with status ',

        3151: f'Failed to connect to the disabled PodNet for vlanif_check payload:  ',
        3152: f'Failed to connect to the disabled PodNet for vlanif_del payload:  ',
        3153: f'Failed to run vlanif_del payload on the disabled PodNet. Payload exited with status ',
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
                'vlanif_check': f'ip netns exec {namespace} ip link show {ifname}.{vlan}',
                'vlanif_del':  f'ip netns exec {namespace} ip link del {ifname}.{vlan}'
        }


        ret = rcc.run(payloads['vlanif_check'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            #If the vlanif already does NOT exists returns info and true state
            return True, fmt.payload_error(ret, f"1101: " + messages[1101]), fmt.successful_payloads
        fmt.add_successful('vlanif_check', ret)

        ret = rcc.run(payloads['vlanif_del'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        fmt.add_successful('vlanif_del', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3150, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1100]
