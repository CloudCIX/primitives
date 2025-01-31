# stdlib
import json
from typing import Tuple, List, Dict, Any
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh, CONNECTION_ERROR, VALIDATION_ERROR
# local
from cloudcix_primitives.utils import load_pod_config, PodnetErrorFormatter, SSHCommsWrapper, write_rule


__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0

def build(
        namespace: str,
        inbound: List[Dict[str, Any]],
        outbound: List[Dict[str, Any]],
        config_file=None,
) -> Tuple[bool, str]:
    """
    description: |
        Creates user defined rules in the PROJECT_IN and PROJECT_OUT user
        chains in the FILTER tale of a project's network name space.

    parameters:
        namespace: |
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        inbound:
          description: |
              list of rule dictionaries for inbound rules to be created in
              PROJECT_IN chain. These dictionaries will be processed by
              cloudcix_primitives.utils.write_rule().
          type: list
          required: true
          properties:
            version:
                type: int
                description:
                required: true
                    IP version. Must be either 4 or 6.
            source:
                description:
                type: string
                required: true
                    Source address with optional CIDR prefix length, e.g. 0.0.0.0/0
            destination:
                description:
                required: true
                    Destination address with optional CIDR prefix length, e.g. 0.0.0.0/0
            protocol:
                description: IP protocol, such as 'tcp', 'udp' or 'any'.
            port:
                description: port number
                required: false
            action:
                description: |
                    action to take if the rule matches. Can be 'accept', 'drop' or 'reject'.
            log:
                description: whether to log matches of the rule.
                type: bool
                required: true
            order:
                description: position of the rule in the chain.
                type: int
                required: true

        outbound:
          description: |
              list of rule dictionaries for outbound rules to be created in
              PROJECT_OUT chain. These dictionaries will be processed by
              cloudcix_primitives.utils.write_rule().
          type: list
          required: true
          properties:
            version:
                type: int
                description:
                required: true
                    IP version. Must be either 4 or 6.
            source:
                description:
                type: string
                required: true
                    Source address with optional CIDR prefix length, e.g. 0.0.0.0/0
            destination:
                description:
                required: true
                    Destination address with optional CIDR prefix length, e.g. 0.0.0.0/0
            protocol:
                description: IP protocol, such as 'tcp', 'udp' or 'any'.
            port:
                description: port number
                required: false
            action:
                description: |
                    action to take if the rule matches. Can be 'accept', 'drop' or 'reject'.
            log:
                description: whether to log matches of the rule.
                type: bool
                required: true
            order:
                description: position of the rule in the chain.
                type: int
                required: true
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    messages = {
    1000: f'1000: Successfully created inbound/outbound user rules in project name space {namespace} on both PodNet nodes.',

    3021: f'Failed to connect to the enabled PodNet for flush_inbound payload: ',
    3022: f'Failed to run flush_inbound payload on the enabled PodNet. Payload exited with status ',
    3023: f'Failed to connect to the enabled PodNet for create_inbound_rule payload (%(payload)s): ',
    3024: f'Failed to run create_inbound_rule payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
    3025: f'Failed to connect to the enabled PodNet for flush_outbound payload: ',
    3026: f'Failed to run flush_outbound payload on the enabled PodNet. Payload exited with status ',
    3027: f'Failed to connect to the enabled PodNet for create_outbound_rule payload (%(payload)s): ',
    3028: f'Failed to run create_outbound_rule payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
    3029: f'Failed to connect to the enabled PodNet for add_final_accept payload (%(payload)s): ',
    3030: f'Failed to run add_final_accept payload (%(payload)s) on the enabled PodNet. Payload exited with status ',

    3061: f'Failed to connect to the disabled PodNet for flush_inbound payload: ',
    3062: f'Failed to run flush_inbound payload on the disabled PodNet. Payload exited with status ',
    3063: f'Failed to connect to the disabled PodNet for create_inbound_rule payload (%(payload)s): ',
    3064: f'Failed to run create_inbound_rule payload (%(payload)s) on the disabled PodNet. Payload exited with status ',
    3065: f'Failed to connect to the disabled PodNet for flush_outbound payload: ',
    3066: f'Failed to run flush_outbound payload on the disabled PodNet. Payload exited with status ',
    3067: f'Failed to connect to the disabled PodNet for create_outbound_rule payload (%(payload)s): ',
    3068: f'Failed to run create_outbound_rule payload (%(payload)s) on the disabled PodNet. Payload exited with status ',
    3069: f'Failed to connect to the disabled PodNet for add_final_accept payload (%(payload)s): ',
    3070: f'Failed to run add_final_accept payload (%(payload)s) on the disabled PodNet. Payload exited with status ',
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
            'flush_inbound': f'ip netns exec {namespace} nft flush chain inet FILTER PROJECT_IN',
            'flush_outbound': f'ip netns exec {namespace} nft flush chain inet FILTER PROJECT_OUT',
            'add_final_accept': f'ip netns exec {namespace} nft add rule inet FILTER PROJECT_OUT accept',
        }

        ret = rcc.run(payloads['flush_inbound'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('flush_inbound', ret)

        for rule in sorted(inbound, key=lambda fw: fw['order']):
            payload = write_rule(namespace=namespace, rule=rule, user_chain='PROJECT_IN')

            ret = rcc.run(payload)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3] % {'payload': payload}), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4] % {'payload': payload}), fmt.successful_payloads
            fmt.add_successful('create_inbound_rule (%s)' % payload, ret)

        ret = rcc.run(payloads['flush_outbound'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+4]), fmt.successful_payloads
        fmt.add_successful('flush_outbound', ret)

        for rule in sorted(outbound, key=lambda fw: fw['order']):
           payload = write_rule(namespace=namespace, rule=rule, user_chain='PROJECT_OUT')

           ret = rcc.run(payload)
           if ret["channel_code"] != CHANNEL_SUCCESS:
               return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+3] % {'payload': payload}), fmt.successful_payloads
           if ret["payload_code"] != SUCCESS_CODE:
               return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+4] % {'payload': payload}), fmt.successful_payloads
           fmt.add_successful('create_outbound_rule (%s)' % payload, ret)

        ret = rcc.run(payloads['add_final_accept'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+9}: " + messages[prefix+9]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+10}: " + messages[prefix+10]), fmt.successful_payloads
        fmt.add_successful('add_final_accept', ret)

        return True, "", fmt.successful_payloads


    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3060, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]


def read() -> Tuple[bool, dict, str]:
    return(False, {}, 'Not Implemented')


def scrub() -> Tuple[bool, str]:
    return(False, {}, 'Not Implemented')
