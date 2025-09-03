# stdlib
import json
from typing import Tuple, List, Dict, Any
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh
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
        rules: List[Dict[str, Any]],
        config_file=None,
) -> Tuple[bool, str]:
    """
    description: |
        Creates user defined rules in the PRVT_2_PRVT user chain in the FILTER table
        of a project's network name space.

    parameters:
        namespace: |
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        rules:
          description: |
              list of rule dictionaries for rules to be created in the PRVT_2_PRVT
              chain. These dictionaries will be processed by
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
    1000: f'1000: Successfully created PRVT_2_PRVT user rules in project name space {namespace} on both PodNet nodes.',

    3021: f'Failed to connect to the enabled PodNet for flush_prvt2prvt payload: ',
    3022: f'Failed to run flush_prvt2prvt payload on the enabled PodNet. Payload exited with status ',
    3023: f'Failed to connect to the enabled PodNet for create_prvt2prvt_rule payload (%(payload)s): ',
    3024: f'Failed to run create_prvt2prvt_rule payload (%(payload)s) on the enabled PodNet. Payload exited with status ',

    3061: f'Failed to connect to the enabled PodNet for flush_prvt2prvt payload: ',
    3062: f'Failed to run flush_prvt2prvt payload on the enabled PodNet. Payload exited with status ',
    3063: f'Failed to connect to the enabled PodNet for create_prvt2prvt_rule payload (%(payload)s): ',
    3064: f'Failed to run create_prvt2prvt_rule payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
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
            'flush_prvt2prvt': f'ip netns exec {namespace} nft flush chain inet FILTER PRVT_2_PRVT',
        }

        ret = rcc.run(payloads['flush_prvt2prvt'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('flush_prvt2prvt', ret)

        for rule in sorted(rules, key=lambda fw: fw['order']):
            payload = write_rule(namespace=namespace, rule=rule, user_chain='PRVT_2_PRVT')

            ret = rcc.run(payload)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3] % {'payload': payload}), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4] % {'payload': payload}), fmt.successful_payloads
            fmt.add_successful('create_prvt2prvt_rule (%s)' % payload, ret)

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
