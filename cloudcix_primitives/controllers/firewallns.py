# stdlib
import ipaddress
import re
# local
from cloudcix_primitives.controllers.exceptions import (
    exception_handler,
    InvalidFirewallRuleAction,
    InvalidFirewallRuleItem,
    InvalidFirewallRuleDestinationType,
    InvalidFirewallRuleDestinationEmpty,
    InvalidFirewallRuleIPAddress,
    InvalidFirewallRulePort,
    InvalidFirewallRuleProtocol,
    InvalidFirewallRuleSingular,
    InvalidFirewallRuleSourceType,
    InvalidFirewallRuleSourceEmpty,
    InvalidFirewallRuleType,
    InvalidFirewallRuleVersion,
    InvalidNATIface,
    InvalidNATIPAddress,
    InvalidNATIPAddressVersion,
    InvalidNATItem,
    InvalidNATPrivate,
    InvalidNATPublic,
    InvalidSetElementsEmpty,
    InvalidSetElementsType,
    InvalidSetItem,
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
        destination = self.rule.get('destination', None)
        if destination is None:
            raise InvalidFirewallRuleItem('destination')
        # check the `destination` type
        if type(destination) is not list:
            raise InvalidFirewallRuleDestinationType(destination)
        if len(destination) == 0:
            raise InvalidFirewallRuleDestinationEmpty(destination)
        #  catch invalid entries for `destination`
        for ip in destination:
            if ip != 'any' and '@' not in ip:
                try:
                    ipaddress.ip_network(ip)
                except (TypeError, ValueError):
                    raise InvalidFirewallRuleIPAddress(ip)
            else:
                # only one item (with `@` or `any`) is allowed
                if len(destination) > 1:
                    raise InvalidFirewallRuleSingular(destination)
        return None

    @exception_handler
    def _validate_source(self):
        source = self.rule.get('source', None)
        if source is None:
            raise InvalidFirewallRuleItem('source')
        # check the `source` type
        if type(source) is not list:
            raise InvalidFirewallRuleSourceType(source)
        if len(source) == 0:
            raise InvalidFirewallRuleSourceEmpty(source)
        # catch invalid entries for `source`
        for ip in source:
            if ip != 'any' and '@' not in ip:
                try:
                    ipaddress.ip_network(ip)
                except (TypeError, ValueError):
                    raise InvalidFirewallRuleIPAddress(ip)
            else:
                # only one item (with `@` or `any`) is allowed
                if len(source) > 1:
                    raise InvalidFirewallRuleSingular(source)
        return None

    @exception_handler
    def _validate_protocol(self):
        protocol = self.rule.get('protocol', None)
        if protocol is None:
            raise InvalidFirewallRuleItem('protocol')
        if protocol not in PROTOCOL_CHOICES:
            raise InvalidFirewallRuleProtocol(protocol)
        return None

    @exception_handler
    def _validate_port(self):
        ports = self.rule.get('port', None)
        if ports is None:
            raise InvalidFirewallRuleItem('port')
        # check the `port` type
        if type(ports) is not list:
            raise InvalidFirewallRulePort(ports)
        # port can be empty list
        # catch invalid entries for `port`
        for port in ports:
            try:
                if '-' in port:
                    items = port.split('-')
                    if len(items) >= 3:
                        raise InvalidFirewallRulePort(port)
                    for item in items:
                        if int(item) not in PORT_RANGE:
                            raise InvalidFirewallRulePort(port)
                elif '@' in port:  # ports set is validated separately
                    # only one set element (with `@`) is allowed
                    if len(ports) > 1:
                        raise InvalidFirewallRuleSingular(port)
                else:
                    if int(port) not in PORT_RANGE:
                        raise InvalidFirewallRulePort(port)
            except (TypeError, ValueError):
                raise InvalidFirewallRulePort(port)
        return None

    @exception_handler
    def _validate_version(self):
        version = self.rule.get('version', None)
        if version is None:
            raise InvalidFirewallRuleItem('version')
        try:
            if int(version) not in [4, 6]:
                raise InvalidFirewallRuleVersion(version)
        except (TypeError, ValueError):
            raise InvalidFirewallRuleVersion(version)
        return None

    @exception_handler
    def _validate_action(self):
        action = self.rule.get('action', None)
        if action is None:
            raise InvalidFirewallRuleItem('action')
        if action not in ['accept', 'drop']:
            raise InvalidFirewallRuleAction(action)
        return None

    @exception_handler
    def _validate_type(self):
        iiface = self.rule.get('iiface', None)
        oiface = self.rule.get('oiface', None)
        if iiface in [None, '', 'none'] and oiface in [None, '', 'none']:
            raise InvalidFirewallRuleType(f'iiface:{iiface};oiface:{oiface}')
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
        name = self.obj.get('name', None)
        if name is None:
            raise InvalidSetItem('name')
        if ' ' in name:  # White spaces in names are not allowed
            raise InvalidSetName(name)
        return None

    @exception_handler
    def _validate_type(self):
        typ = self.obj.get('type', None)
        if typ is None:
            raise InvalidSetItem('type')
        if typ not in SET_TYPES:
            raise InvalidSetType(typ)
        return None

    @exception_handler
    def _validate_elements(self):
        typ = self.obj.get('type', None)
        if typ is None:
            raise InvalidSetItem('type')

        elements = self.obj.get('elements', None)
        if elements is None:
            raise InvalidSetItem('elements')

        if type(elements) is not list:
            raise InvalidSetElementsType(elements)

        if len(elements) == 0:
            raise InvalidSetElementsEmpty(elements)

        if typ == 'ipv4_addr':
            for element in elements:
                try:
                    ip = ipaddress.ip_network(element)
                    if ip.version != 4:
                        raise InvalidSetIPAddressVersion(element)
                except (TypeError, ValueError):
                    raise InvalidSetIPAddress(element)
        elif typ == 'ipv6_addr':
            for element in elements:
                try:
                    ip = ipaddress.ip_network(element)
                    if ip.version != 6:
                        raise InvalidSetIPAddressVersion(element)
                except (TypeError, ValueError):
                    raise InvalidSetIPAddress(element)
        elif typ == 'ether_addr':
            for element in elements:
                if is_valid_mac(element) is False:
                    raise InvalidSetMacAddress(element)
        elif typ == 'inet_service':
            for element in elements:
                try:
                    if '-' in element:
                        items = element.split('-')
                        if len(items) >= 3:
                            raise InvalidSetPort(element)
                        for item in items:
                            if int(item) not in PORT_RANGE:
                                raise InvalidSetPortValue(element)
                    else:
                        if int(element) not in PORT_RANGE:
                            raise InvalidSetPortValue(element)
                except (TypeError, ValueError):
                    raise InvalidSetPortValue(element)
        else:
            raise InvalidSetType(typ)


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
        iface = self.nat.get('iface', None)
        if iface is None:
            raise InvalidNATItem('iface')
        if ' ' in iface:  # White spaces in iface are not allowed
            raise InvalidNATIface(iface)
        return None

    @exception_handler
    def _validate_private(self):
        private = self.nat.get('private', None)
        if private is None:
            raise InvalidNATItem('private')
        try:
            ip = ipaddress.ip_network(private)
            if ip.version != 4:
                raise InvalidNATIPAddressVersion(private)
            if ip.is_private is False:
                raise InvalidNATPrivate(private)
        except (TypeError, ValueError):
            raise InvalidNATIPAddress(private)

    @exception_handler
    def _validate_public(self):
        public = self.nat.get('public', None)
        if public is None:
            raise InvalidNATItem('public')
        try:
            ip = ipaddress.ip_network(public)
            if ip.version != 4:
                raise InvalidNATIPAddressVersion(public)
            if ip.is_private is True:
                raise InvalidNATPublic(public)
        except (TypeError, ValueError):
            raise InvalidNATIPAddress(public)
