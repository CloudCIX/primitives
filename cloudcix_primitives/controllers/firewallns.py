# stdlib
import ipaddress
import re
# local
from cloudcix_primitives.exceptions import (
    exception_handler,
    InvalidFirewallRuleAction,
    InvalidFirewallRuleDestination,
    InvalidFirewallRuleIPAddress,
    InvalidFirewallRulePort,
    InvalidFirewallRuleProtocol,
    InvalidFirewallRuleSource,
    InvalidFirewallRuleType,
    InvalidFirewallRuleVersion,
    InvalidNATIface,
    InvalidNATIPAddress,
    InvalidNATIPAddressVersion,
    InvalidNATPrivate,
    InvalidNATPublic,
    InvalidSetName,
    InvalidSetType,
    InvalidSetIPAddressVersion,
    InvalidSetIPAddress,
    InvalidSetMacAddress,
    InvalidSetPort,
    InvalidSetPortValue,
)

PORT_RANGE = range(1, 65536)
PROTOCOL_CHOICES = ['any', 'tcp', 'udp', 'icmp', 'dns', 'vpn']
SET_TYPES = ['ipv4_addr', 'ipv6_addr', 'inet_service', 'ether_addr']

__all__ = ['FirewallNamespace', 'FirewallNAT', 'FirewallSet']


def is_valid_mac(mac_address):
    # Define the regex pattern for MAC addresses
    pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'

    # Use fullmatch to check if the entire string matches the pattern, if not matches result is None
    return re.fullmatch(pattern, mac_address) is not None


class FirewallNamespace:
    rule: dict
    success: bool
    errors: list

    def __init__(self, rule) -> None:
        self.rule = rule
        self.success = True
        self.errors = []

    def __call__(self):
        validators = [
            self._validate_action,
            self._validate_version,
            self._validate_destination,
            self._validate_source,
            self._validate_protocol,
            self._validate_port,
            self._validate_type,
        ]

        for validator in validators:
            error = validator()
            if error is not None:
                self.success = False
                self.errors.append(str(error))

        return self.success, self.errors

    @exception_handler
    def _validate_destination(self):
        if self.rule['destination'] is None:
            return None
        # check the `destination` type
        if type(self.rule['destination']) is not list:
            raise InvalidFirewallRuleDestination
        #  catch invalid entries for `destination`
        for ip in self.rule['destination']:
            if ip != 'any' or '@' not in ip:
                try:
                    ipaddress.ip_network(ip)
                except (TypeError, ValueError):
                    raise InvalidFirewallRuleIPAddress
        return None

    @exception_handler
    def _validate_source(self):
        if self.rule['source'] is None:
            return None
        # check the `source` type
        if type(self.rule['source']) is not list:
            raise InvalidFirewallRuleSource
        # catch invalid entries for `source`
        for ip in self.rule['source']:
            if ip != 'any' or '@' not in ip:
                try:
                    ipaddress.ip_network(ip)
                except (TypeError, ValueError):
                    raise InvalidFirewallRuleIPAddress
        return None

    @exception_handler
    def _validate_protocol(self):
        if self.rule['protocol'] not in PROTOCOL_CHOICES:
            raise InvalidFirewallRuleProtocol
        return None

    @exception_handler
    def _validate_port(self):
        if self.rule['port'] is None:
            return None
        # check the `port` type
        if type(self.rule['port']) is not list:
            raise InvalidFirewallRulePort
        # catch invalid entries for `port`
        for prt in self.rule['port']:
            try:
                if '-' in prt:
                    items = prt.split('-')
                    if len(items) >= 3:
                        raise InvalidFirewallRulePort
                    for item in items:
                        if int(item) not in PORT_RANGE:
                            raise InvalidFirewallRulePort
                elif '@' in prt:  # ports set is validated separately
                    pass
                else:
                    if int(prt) not in PORT_RANGE:
                        raise InvalidFirewallRulePort
            except (TypeError, ValueError):
                raise InvalidFirewallRulePort
        return None

    @exception_handler
    def _validate_version(self):
        try:
            if int(self.rule['version']) not in [4, 6]:
                raise InvalidFirewallRuleVersion
        except (TypeError, ValueError):
            raise InvalidFirewallRuleVersion
        return None

    @exception_handler
    def _validate_action(self):
        if self.rule['action'] not in ['accept', 'drop']:
            raise InvalidFirewallRuleAction
        return None

    @exception_handler
    def _validate_type(self):
        if self.rule['iiface'] in [None, '', 'none'] and self.rule['oiface'] in [None, '', 'none']:
            raise InvalidFirewallRuleType
        return None


class FirewallSet:
    obj: dict
    success: bool
    errors: list

    def __init__(self, obj) -> None:
        self.obj = obj
        self.success = True
        self.errors = []

    def __call__(self):
        validators = [
            self._validate_name,
            self._validate_type,
            self._validate_elements,
        ]

        for validator in validators:
            error = validator()
            if error is not None:
                self.success = False
                self.errors.append(str(error))

        return self.success, self.errors

    @exception_handler
    def _validate_name(self):
        if ' ' in self.obj['name']:  # White spaces in names are not allowed
            raise InvalidSetName
        return None

    @exception_handler
    def _validate_type(self):
        if self.obj['type'] not in SET_TYPES:
            raise InvalidSetType
        return None

    @exception_handler
    def _validate_elements(self):
        if self.obj['type'] == 'ipv4_addr':
            for element in self.obj['elements']:
                try:
                    ip = ipaddress.ip_network(element)
                    if ip.version != 4:
                        raise InvalidSetIPAddressVersion
                except (TypeError, ValueError):
                    raise InvalidSetIPAddress
        elif self.obj['type'] == 'ipv6_addr':
            for element in self.obj['elements']:
                try:
                    ip = ipaddress.ip_network(element)
                    if ip.version != 6:
                        raise InvalidSetIPAddressVersion
                except (TypeError, ValueError):
                    raise InvalidSetIPAddress
        elif self.obj['type'] == 'ether_addr':
            for element in self.obj['elements']:
                if is_valid_mac(element) is False:
                    raise InvalidSetMacAddress
        elif self.obj['type'] == 'inet_service':
            for element in self.obj['elements']:
                try:
                    if '-' in element:
                        items = element.split('-')
                        if len(items) >= 3:
                            raise InvalidSetPort
                        for item in items:
                            if int(item) not in PORT_RANGE:
                                raise InvalidSetPortValue
                    else:
                        if int(element) not in PORT_RANGE:
                            raise InvalidSetPortValue
                except (TypeError, ValueError):
                    raise InvalidSetPortValue
        else:
            raise InvalidSetType


class FirewallNAT:
    nat: dict
    success: bool
    errors: list

    def __init__(self, nat) -> None:
        self.nat = nat
        self.success = True
        self.errors = []

    def __call__(self):
        validators = [
            self._validate_private,
            self._validate_public,
            self._validate_iface,
        ]

        for validator in validators:
            error = validator()
            if error is not None:
                self.success = False
                self.errors.append(str(error))

        return self.success, self.errors

    @exception_handler
    def _validate_iface(self):
        if ' ' in self.nat['iface']:  # White spaces in iface are not allowed
            raise InvalidNATIface
        return None

    @exception_handler
    def _validate_private(self):
        try:
            ip = ipaddress.ip_network(self.nat['private'])
            if ip.version != 4:
                raise InvalidNATIPAddressVersion
            if ip.is_private is False:
                raise InvalidNATPrivate
        except (TypeError, ValueError):
            raise InvalidNATIPAddress

    @exception_handler
    def _validate_public(self):
        try:
            ip = ipaddress.ip_network(self.nat['public'])
            if ip.version != 4:
                raise InvalidNATIPAddressVersion
            if ip.is_private is True:
                raise InvalidNATPublic
        except (TypeError, ValueError):
            raise InvalidNATIPAddress
