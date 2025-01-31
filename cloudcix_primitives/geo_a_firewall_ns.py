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
        inbound: List[str],
        outbound: List[str],
        config_file=None,
) -> Tuple[bool, str]:
    """
    description: |
        Creates user defined rules in the GEO_IN_ALLOW and GEO_OUT_ALLOW user
        chains in the FILTER tale of a project's network name space.

    parameters:
        namespace: |
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        inbound:
          description: |
              list of GeoIP address sets to allow as destinations for outbund
              traffic. All sets listed must exist. Can be empty.
          type: list
          required: true

        outbound:
          description: |
              list of GeoIP address sets to allow as destinations for outbund
              traffic. All sets listed must exist. Can be empty.
          type: list
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
    3023: f'Failed to connect to the enabled PodNet for add_inbound_set payload (%(payload)s): ',
    3024: f'Failed to run add_inbound_set payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
    3025: f'Failed to connect to the enabled PodNet for add_inbound_drop payload (%(payload)s): ',
    3036: f'Failed to run add_inbound_drop payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
    3067: f'Failed to connect to the enabled PodNet for flush_outbound payload: ',
    3028: f'Failed to run flush_outbound payload on the enabled PodNet. Payload exited with status ',
    3029: f'Failed to connect to the enabled PodNet for add_outbound_set payload (%(payload)s): ',
    3030: f'Failed to run add_outbound_set payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
    3031: f'Failed to connect to the enabled PodNet for add_outbound_drop payload (%(payload)s): ',
    3032: f'Failed to run add_outbound_drop payload (%(payload)s) on the enabled PodNet. Payload exited with status ',

    3061: f'Failed to connect to the disabled PodNet for flush_inbound payload: ',
    3062: f'Failed to run flush_inbound payload on the disabled PodNet. Payload exited with status ',
    3063: f'Failed to connect to the disabled PodNet for add_inbound_set payload (%(payload)s): ',
    3064: f'Failed to run add_inbound_set payload (%(payload)s) on the disabled PodNet. Payload exited with status ',
    3065: f'Failed to connect to the disabled PodNet for add_inbound_drop payload (%(payload)s): ',
    3036: f'Failed to run add_inbound_drop payload (%(payload)s) on the disabled PodNet. Payload exited with status ',
    3067: f'Failed to connect to the disabled PodNet for flush_outbound payload: ',
    3068: f'Failed to run flush_outbound payload on the disabled PodNet. Payload exited with status ',
    3069: f'Failed to connect to the disabled PodNet for add_outbound_set payload (%(payload)s): ',
    3070: f'Failed to run add_outbound_set payload (%(payload)s) on the disabled PodNet. Payload exited with status ',
    3071: f'Failed to connect to the disabled PodNet for add_outbound_drop payload (%(payload)s): ',
    3072: f'Failed to run add_outbound_drop payload (%(payload)s) on the disabled PodNet. Payload exited with status ',
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
        
        rule_templates = {
            'add_inbound_set': f'ip netns exec {namespace} nft add rule inet FILTER GEO_IN_ALLOW ip%(ip_version)s saddr @%(set)s accept',
            'add_outbound_set': f'ip netns exec {namespace} nft add rule inet FILTER GEO_OUT_ALLOW ip%(ip_version)s saddr @%(set)s accept',
        }

        payloads = {
            'flush_inbound': f'ip netns exec {namespace} nft flush chain inet FILTER GEO_IN_ALLOW',
            'add_inbound_drop': f'ip netns exec {namespace} nft add rule inet FILTER GEO_IN_ALLOW drop',
            'flush_outbound': f'ip netns exec {namespace} nft flush chain inet FILTER GEO_OUT_ALLOW',
            'add_outbound_drop': f'ip netns exec {namespace} nft add rule inet FILTER GEO_OUT_ALLOW drop',
        }

        ret = rcc.run(payloads['flush_inbound'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('flush_inbound', ret)

        for address_set in inbound:
            if address_set.endswith('_V4'):
                ip_version = ''
            if address_set.endswith('_V6'):
                ip_version = '6'

            payload = rule_templates['add_inbound_set'] % {'set': address_set, 'ip_version': ip_version}

            ret = rcc.run(payload)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3] % {'payload': payload}), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4] % {'payload': payload}), fmt.successful_payloads
            fmt.add_successful('add_inbound_set (%s)' % payload, ret)

        if (len(inbound) > 0):
            ret = rcc.run(payloads['add_inbound_drop'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
            fmt.add_successful('add_inbound_drop', ret)

        ret = rcc.run(payloads['flush_outbound'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
        fmt.add_successful('flush_outbound', ret)

        for address_set in outbound:
            if address_set.endswith('_V4'):
                ip_version = ''
            if address_set.endswith('_V6'):
                ip_version = '6'

            payload = rule_templates['add_outbound_set'] % {'set': address_set, 'ip_version': ip_version}

            ret = rcc.run(payload)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+9}: " + messages[prefix+9] % {'payload': payload}), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+10}: " + messages[prefix+10] % {'payload': payload}), fmt.successful_payloads
            fmt.add_successful('add_outbound_set (%s)' % payload, ret)

        if (len(outbound) > 0):
            ret = rcc.run(payloads['add_outbound_drop'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+11}: " + messages[prefix+11]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+12}: " + messages[prefix+12]), fmt.successful_payloads
            fmt.add_successful('add_outbound_drop', ret)

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
