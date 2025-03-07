# stdlib
import json
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
        namespace: str,
        public_bridge: str,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Builds nftables tables, base chains, user chains, interface sets, jump
        rules and default base chain rules required for a CloudCIX project.
        Throughout the life time of a project, the base chains are never
        modified by another primitive. The user chains are managed by user
        chain primitives such as project_firewall_ns or nat_firewall_ns.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        public_bridge:
          description: the name space's public bridge interface's name, such as 'br-B1'.
          type: string
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
        1000: f'1000: Successfully created default firewall in project name space {namespace} on both PodNet nodes.',

        3021: f'Failed to connect to the enabled PodNet for flush_ruleset payload: ',
        3022: f'Failed to run flush_ruleset payload on the enabled PodNet. Payload exited with status ',
        3023: f'Failed to connect to the enabled PodNet for create_nat_table payload: ',
        3024: f'Failed to run create_nat_table payload on the enabled PodNet. Payload exited with status ',
        3025: f'Failed to connect to the enabled PodNet for create_filter_table payload: ',
        3026: f'Failed to run create_filter_table payload on the enabled PodNet. Payload exited with status ',
        3027: f'Failed to connect to the enabled PodNet for create_nat_postrouting_chain payload: ',
        3028: f'Failed to run create_nat_postrouting_chain payload on the enabled PodNet. Payload exited with status ',
        3029: f'Failed to connect to the enabled PodNet for create_nat_prerouting_chain payload: ',
        3030: f'Failed to run create_nat_prerouting_chain payload on the enabled PodNet. Payload exited with status ',
        3031: f'Failed to connect to the enabled PodNet for create_filter_postrouting_chain payload: ',
        3032: f'Failed to run create_filter_postrouting_chain payload on the enabled PodNet. Payload exited with status ',
        3033: f'Failed to connect to the enabled PodNet for create_filter_prerouting_chain payload: ',
        3034: f'Failed to run create_filter_prerouting_chain payload on the enabled PodNet. Payload exited with status ',
        3035: f'Failed to connect to the enabled PodNet for create_filter_output_chain payload: ',
        3036: f'Failed to run create_filter_output_chain payload on the enabled PodNet. Payload exited with status ',
        3037: f'Failed to connect to the enabled PodNet for create_filter_input_chain payload: ',
        3038: f'Failed to run create_filter_input_chain payload on the enabled PodNet. Payload exited with status ',
        3039: f'Failed to connect to the enabled PodNet for create_filter_forward_chain payload: ',
        3040: f'Failed to run create_filter_forward_chain payload on the enabled PodNet. Payload exited with status ',
        3041: f'Failed to connect to the enabled PodNet for create_interface_set %(set_name)s payload (%(payload)s): ',
        3042: f'Failed to run create_interface_set %(set_name)s payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
        3043: f'Failed to connect to the enabled PodNet for create_user_chain %(chain)s payload (%(payload)s): ',
        3044: f'Failed to run create_user_chain %(chain)s payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
        3045: f'Failed to connect to the enabled PodNet for create_rule payload (%(payload)s): ',
        3046: f'Failed to run create_rule payload (%(payload)s) on the enabled PodNet. Payload exited with status ',

        3061: f'Failed to connect to the disabled PodNet for flush_ruleset payload: ',
        3062: f'Failed to run flush_ruleset payload on the disabled PodNet. Payload exited with status ',
        3063: f'Failed to connect to the disabled PodNet for create_nat_table payload: ',
        3064: f'Failed to run create_nat_table payload on the disabled PodNet. Payload exited with status ',
        3065: f'Failed to connect to the disabled PodNet for create_filter_table payload: ',
        3066: f'Failed to run create_filter_table payload on the disabled PodNet. Payload exited with status ',
        3067: f'Failed to connect to the disabled PodNet for create_nat_postrouting_chain payload: ',
        3068: f'Failed to run create_nat_postrouting_chain payload on the disabled PodNet. Payload exited with status ',
        3069: f'Failed to connect to the disabled PodNet for create_nat_prerouting_chain payload: ',
        3070: f'Failed to run create_nat_prerouting_chain payload on the disabled PodNet. Payload exited with status ',
        3071: f'Failed to connect to the disabled PodNet for create_filter_postrouting_chain payload: ',
        3072: f'Failed to run create_filter_postrouting_chain payload on the disabled PodNet. Payload exited with status ',
        3073: f'Failed to connect to the disabled PodNet for create_filter_prerouting_chain payload: ',
        3074: f'Failed to run create_filter_prerouting_chain payload on the disabled PodNet. Payload exited with status ',
        3075: f'Failed to connect to the disabled PodNet for create_filter_output_chain payload: ',
        3076: f'Failed to run create_filter_output_chain payload on the disabled PodNet. Payload exited with status ',
        3077: f'Failed to connect to the disabled PodNet for create_filter_input_chain payload: ',
        3078: f'Failed to run create_filter_input_chain payload on the disabled PodNet. Payload exited with status ',
        3079: f'Failed to connect to the disabled PodNet for create_filter_forward_chain payload: ',
        3080: f'Failed to run create_filter_forward_chain payload on the disabled PodNet. Payload exited with status ',
        3081: f'Failed to connect to the disabled PodNet for create_interface_set payload (%(payload)s): ',
        3082: f'Failed to run create_interface_set payload (%(payload)s) on the disabled PodNet. Payload exited with status ',
        3083: f'Failed to connect to the disabled PodNet for create_user_chain payload (%(payload)s): ',
        3084: f'Failed to run create_user_chain payload (%(payload)s) on the disabled PodNet. Payload exited with status ',
        3085: f'Failed to connect to the disabled PodNet for create_rule payload (%(payload)s): ',
        3086: f'Failed to run create_rule payload (%(payload)s) on the disabled PodNet. Payload exited with status ',
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

        interface_sets = [
            'PRIVATE',
            'S2S_TUNNEL',
            'DYN_TUNNEL',
        ]

        user_chains = [
            'GEO_IN_ALLOW',
            'GEO_IN_BLOCK',
            'GEO_OUT_ALLOW',
            'GEO_OUT_BLOCK',
            'PROJECT_OUT',
            'PROJECT_IN',
            'VPNS2S',
            'VPNDYN',
            'PRVT_2_PRVT',
        ]

        rules = [
            # INPUT
            f'ip netns exec {namespace} nft add rule inet FILTER INPUT '
            f'ct state established,related accept',

            f'ip netns exec {namespace} nft add rule inet FILTER INPUT '
            'icmp type { echo-reply, destination-unreachable, echo-request, time-exceeded } accept',

            f'ip netns exec {namespace} nft add rule inet FILTER INPUT '
            'icmpv6 type { echo-request, mld-listener-query, nd-router-solicit, nd-router-advert, nd-neighbor-solicit, nd-neighbor-advert } accept',

            f'ip netns exec {namespace} nft add rule inet FILTER INPUT '
            'meta l4proto { tcp, udp } th dport 53 accept',

            f'ip netns exec {namespace} nft add rule inet FILTER INPUT '
            'udp dport {500, 4500} accept',

            f'ip netns exec {namespace} nft add rule inet FILTER INPUT '
            'ip protocol esp accept',

            # PREROUTING
            f'ip netns exec {namespace} nft add rule inet FILTER PREROUTING '
            'ct state established,related accept',

            f'ip netns exec {namespace} nft add rule inet FILTER PREROUTING '
            f'iifname {namespace}.{public_bridge} jump GEO_IN_ALLOW',

            f'ip netns exec {namespace} nft add rule inet FILTER PREROUTING '
            f'iifname {namespace}.{public_bridge} jump GEO_IN_BLOCK',


            # POSTROUTING
            f'ip netns exec {namespace} nft add rule inet FILTER POSTROUTING '
            'ct state established,related accept',

            f'ip netns exec {namespace} nft add rule inet FILTER POSTROUTING '
            f'oifname {namespace}.{public_bridge} jump GEO_OUT_ALLOW',

            f'ip netns exec {namespace} nft add rule inet FILTER POSTROUTING '
            f'oifname {namespace}.{public_bridge} jump GEO_OUT_BLOCK',

            # FORWARD
            f'ip netns exec {namespace} nft add rule inet FILTER FORWARD '
            'ct state established,related accept',

            f'ip netns exec {namespace} nft add rule inet FILTER FORWARD '
            f'iifname @PRIVATE oifname {namespace}.{public_bridge} jump PROJECT_OUT',

            f'ip netns exec {namespace} nft add rule inet FILTER FORWARD '
            f'iifname {namespace}.{public_bridge} oifname @PRIVATE jump PROJECT_IN',

            f'ip netns exec {namespace} nft add rule inet FILTER FORWARD '
            'iifname @PRIVATE oifname @S2S_TUNNEL jump VPNS2S',

            f'ip netns exec {namespace} nft add rule inet FILTER FORWARD '
            'iifname @S2S_TUNNEL oifname @PRIVATE jump VPNS2S',

            f'ip netns exec {namespace} nft add rule inet FILTER FORWARD '
            'iifname @PRIVATE oifname @DYN_TUNNEL jump VPNDYN',

            f'ip netns exec {namespace} nft add rule inet FILTER FORWARD '
            'iifname @DYN_TUNNEL oifname @PRIVATE jump VPNDYN',

            f'ip netns exec {namespace} nft add rule inet FILTER FORWARD '
            'iifname @PRIVATE oifname @PRIVATE jump PRVT_2_PRVT',

        ]

        payloads = {
            'flush_ruleset': f'ip netns exec {namespace} nft flush ruleset',

            'create_nat_table': f'ip netns exec {namespace} '
                                'nft add table ip NAT',
            'create_filter_table': f'ip netns exec {namespace} '
                                   'nft add table inet FILTER',

            'create_nat_postrouting_chain': f'ip netns exec {namespace} '
                                            'nft add chain ip NAT POSTROUTING '
                                            '{ type nat hook postrouting priority 100 \\; policy accept \\; }',
            'create_nat_prerouting_chain': f'ip netns exec {namespace} '
                                           'nft add chain ip NAT PREROUTING '
                                           '{ type nat hook prerouting priority -100 \\; policy accept \\; }',

            'create_filter_postrouting_chain': f'ip netns exec {namespace} nft add chain inet '
                                              'FILTER POSTROUTING '
                                              '{ type filter hook postrouting priority 0 \\; policy accept \\; }',
            'create_filter_prerouting_chain': f'ip netns exec {namespace} nft add chain inet '
                                              'FILTER PREROUTING '
                                              '{ type filter hook prerouting priority 0 \\; policy accept \\; }',
            'create_filter_output_chain': f'ip netns exec {namespace} nft '
                                          'add chain inet FILTER OUTPUT '
                                          '{ type filter hook output priority 0 \\; policy accept \\; }',
            'create_filter_input_chain': f'ip netns exec {namespace} '
                                         'nft add chain inet FILTER INPUT '
                                         '{ type filter hook input priority 0 \\; policy drop \\; }',
            'create_filter_forward_chain': f'ip netns exec {namespace} '
                                           'nft add chain inet FILTER FORWARD '
                                           '{ type filter hook forward priority 0 \\; policy drop \\; }',
            'create_interface_set': f'ip netns exec {namespace} '
                                       'nft add set inet FILTER %(set_name)s { type ifname\\; }',
            'create_user_chain': f'ip netns exec {namespace} '
                                 'nft add chain inet FILTER %(chain_name)s',
        }

        ret = rcc.run(payloads['flush_ruleset'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('flush_ruleset', ret)

        ret = rcc.run(payloads['create_nat_table'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        fmt.add_successful('create_nat_table', ret)

        ret = rcc.run(payloads['create_filter_table'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6]), fmt.successful_payloads
        fmt.add_successful('create_filter_table', ret)

        ret = rcc.run(payloads['create_nat_postrouting_chain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8]), fmt.successful_payloads
        fmt.add_successful('create_nat_postrouting_chain', ret)

        ret = rcc.run(payloads['create_nat_prerouting_chain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+9}: " + messages[prefix+9]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+10}: " + messages[prefix+10]), fmt.successful_payloads
        fmt.add_successful('create_nat_prerouting_chain', ret)

        ret = rcc.run(payloads['create_filter_postrouting_chain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+11}: " + messages[prefix+11]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+12}: " + messages[prefix+12]), fmt.successful_payloads
        fmt.add_successful('create_filter_postrouting_chain', ret)

        ret = rcc.run(payloads['create_filter_prerouting_chain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+13}: " + messages[prefix+13]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+14}: " + messages[prefix+14]), fmt.successful_payloads
        fmt.add_successful('create_filter_prerouting_chain', ret)

        ret = rcc.run(payloads['create_filter_output_chain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+15}: " + messages[prefix+15]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+16}: " + messages[prefix+16]), fmt.successful_payloads
        fmt.add_successful('create_filter_output_chain', ret)

        ret = rcc.run(payloads['create_filter_input_chain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+17}: " + messages[prefix+17]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+18}: " + messages[prefix+18]), fmt.successful_payloads
        fmt.add_successful('create_filter_input_chain', ret)

        ret = rcc.run(payloads['create_filter_forward_chain'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+19}: " + messages[prefix+19]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+20}: " + messages[prefix+20]), fmt.successful_payloads
        fmt.add_successful('create_filter_forward_chain', ret)

        for set_name in interface_sets:
            payload = payloads['create_interface_set'] % {'set_name': set_name}
            ret = rcc.run(payload)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+21}: " + messages[prefix+21] % {'payload': payload, 'set_name': set_name}), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+22}: " + messages[prefix+22] % {'payload': payload, 'set_name': set_name}), fmt.successful_payloads
            fmt.add_successful('create_interface_set %s' % set_name, ret)

        for chain in user_chains:
            payload = payloads['create_user_chain'] % {'chain_name': chain}
            ret = rcc.run(payload)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+23}: " + messages[prefix+23] % {'payload': payload, 'chain': chain}), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+24}: " + messages[prefix+24] % {'payload': payload, 'chain': chain}), fmt.successful_payloads
            fmt.add_successful('create_user_chain %s' % chain, ret)

        for rule in rules:
            ret = rcc.run(rule)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+25}: " + messages[prefix+25] % {'payload': rule}), fmt.successful_payloads
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+26}: " + messages[prefix+26] % {'payload': rule}), fmt.successful_payloads
            fmt.add_successful('create_rule (%s)' % rule, ret)

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


def scrub(
    namespace: str,
    config_file=None
    ) -> Tuple[bool, str]:
    """
    description:
        Builds nftables tables, base chains, user chains, interface sets, jump
        rules and default base chain rules required for a CloudCIX project.
        Throughout the life time of a project, the base chains are never
        modified by another primitive. The user chains are managed by user
        chain primitives such as project_firewall_ns or nat_firewall_ns.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        public_bridge:
          description: the name space's public bridge interface's name, such as 'br-B1'.
          type: string
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
    1000: f'1000: Successfully scrubbed default firewall in project name space {namespace} on both PodNet nodes.',

    3121: f'Failed to connect to the enabled PodNet for flush_ruleset payload: ',
    3122: f'Failed to run flush_ruleset payload on the enabled PodNet. Payload exited with status ',
    3161: f'Failed to connect to the disabled PodNet for flush_ruleset payload: ',
    3162: f'Failed to run flush_ruleset payload on the disabled PodNet. Payload exited with status ',
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
            'flush_ruleset': f'ip netns exec {namespace} nft flush ruleset'
        }

        ret = rcc.run(payloads['flush_ruleset'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('flush_ruleset', ret)
        return True, "", fmt.successful_payloads


    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3160, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]
