# stdlib
import ipaddress
# local
from ..exceptions import (
    exception_handler,
    InvalidFirewallRuleAction,
    InvalidFirewallRuleDestination,
    InvalidFirewallRuleIPAddress,
    InvalidFirewallRulePort,
    InvalidFirewallRuleProtocol,
    InvalidFirewallRuleSource,
    InvalidFirewallRuleType,
    InvalidFirewallRuleVersion,
)

PORT_RANGE = range(1, 65536)
PROTOCOL_CHOICES = ['any', 'tcp', 'udp', 'icmp', 'dns', 'vpn']

__all__ = ['FirewallNamespace']


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
            if ip != 'any':
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
            if ip != 'any':
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
                        return InvalidFirewallRulePort
                    for item in items:
                        if int(item) not in PORT_RANGE:
                            return InvalidFirewallRulePort
                else:
                    if int(prt) not in PORT_RANGE:
                        return InvalidFirewallRulePort
            except (TypeError, ValueError):
                return InvalidFirewallRulePort
        return None

    @exception_handler
    def _validate_version(self):
        try:
            if int(self.rule['version']) not in [4, 6]:
                raise InvalidFirewallRuleVersion
        except (TypeError, ValueError):
            return InvalidFirewallRuleVersion
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
