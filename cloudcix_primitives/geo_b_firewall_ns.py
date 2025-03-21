# stdlib
import json
from typing import Tuple, List, TypedDict
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh, CONNECTION_ERROR, VALIDATION_ERROR
# local
from cloudcix_primitives.utils import load_pod_config, PodnetErrorFormatter, SSHCommsWrapper


__all__ = [
    'build',
    'read',
]

SUCCESS_CODE = 0

AddressSet = TypedDict('AddressSet', {'name': str, 'version': int})

def build(
    namespace: str,
    inbound: List[AddressSet],
    outbound: List[AddressSet],
    config_file=None
) -> Tuple[bool, str]:
    """
    description:
        Adds the nftables sets inbound and outbound to the GEO_IN_BLOCK and GEO_OUT_BLOCK packet dropping chains respectively.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453'
            type: string
            required: true
        inbound:
            description: list of nftable sets to add to the GEO_IN_BLOCK chain.
            type: list
            required: true
        outbound:
            description: list of nftable sets to add to the GEO_OUT_BLOCK chain.
            type: list
            required: true
        config_file:
            description: path to the config.json file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and 
            the output or error message.
        type: tuple
    """
    messages = {
        1000: f'1000: Successfully created block rulesets in namespace {namespace}',

        3021: f'3021: Failed to connect to the enabled PodNet for flush_in_chain payload:  ',
        3022: f'3022: Failed to flush GEO_IN_BLOCK chain in namespace {namespace} on the enabled PodNet for payload flush_in_chain:  ',
        3023: f'3023: Failed to connect to the enabled PodNet for flush_out_chain payload:  ',
        3024: f'3024: Failed to flush GEO_OUT_BLOCK chain in namespace {namespace} on the enabled PodNet for payload flush_out_chain:  ',
        3025: f'3025: Failed to connect to the enabled PodNet for create_inbound_rule payload:  ',
        3026: f'3026: Failed to create inbound block rule in namespace {namespace} on the enabled PodNet for payload create_inbound_rule:  ',
        3027: f'3027: Failed to connect to the enabled PodNet for create_outbound_rule payload:  ',
        3028: f'3028: Failed to create outbound block rule in namespace {namespace} on the enabled PodNet for payload create_outbound_rule:  ',

        3051: f'3051: Failed to connect to the disabled PodNet for flush_in_chain payload:  ',
        3052: f'3052: Failed to flush GEO_IN_BLOCK chain in namespace {namespace} on the disabled PodNet for payload flush_in_chain:  ',
        3053: f'3053: Failed to connect to the disabled PodNet for flush_out_chain payload:  ',
        3054: f'3054: Failed to flush GEO_OUT_BLOCK chain in namespace {namespace} on the disabled PodNet for payload flush_out_chain:  ',
        3055: f'3055: Failed to connect to the disabled PodNet for create_inbound_rule payload:  ',
        3056: f'3056: Failed to create inbound block rule in namespace {namespace} on the disabled PodNet for payload create_inbound_rule:  ',
        3057: f'3057: Failed to connect to the disabled PodNet for create_outbound_rule payload:  ',
        3058: f'3058: Failed to create outbound block rule in namespace {namespace} on the disabled PodNet for payload create_outbound_rule:  ',
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
            'flush_in_chain': f'ip netns exec {namespace} nft flush chain inet FILTER GEO_IN_BLOCK',
            'flush_out_chain': f'ip netns exec {namespace} nft flush chain inet FILTER GEO_OUT_BLOCK',
            'create_inbound_rule': f'ip netns exec {namespace} nft add rule inet FILTER GEO_IN_BLOCK '
                                    'ip%(ip_version)s saddr @%(set_name)s drop',
            'create_outbound_rule': f'ip netns exec {namespace} nft add rule inet FILTER GEO_OUT_BLOCK '
                                    'ip%(ip_version)s daddr @%(set_name)s drop'
        }

        ret = rcc.run(payloads['flush_in_chain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('flush_in_chain', ret)

        for inb in inbound:
            if inb['version'] == 4:
                ip_version = ''
            elif inb['version'] == 6:
                ip_version = '6'

            ret = rcc.run(payloads['create_inbound_rule'] % {'set_name': inb['name'], 'ip_version': ip_version})
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
            fmt.add_successful('create_inbound_rule', ret)

        ret = rcc.run(payloads['flush_out_chain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        fmt.add_successful('flush_out_chain', ret)

        for out in outbound:
            if out['version'] == 4:
                ip_version = ''
            elif out['version'] == 6:
                ip_version = '6'

            ret = rcc.run(payloads['create_outbound_rule'] % {'set_name': out['name'], 'ip_version': ip_version})
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
            fmt.add_successful('create_outbound_rule', ret)

        return True, "", fmt.successful_payloads
    
    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg
    
    status, msg, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if status == False:
        return status, msg
    
    return True, messages[1000]


def read() -> Tuple[bool, dict, str]:
    return(False, {}, 'Not Implemented')
