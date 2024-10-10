def exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseException as e:
            return str(e)
    return wrapper


class InvalidFirewallRuleAction(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule action, Value: {self.obj}'


class InvalidFirewallRuleDestination(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule destination, Value: {self.obj}'


class InvalidFirewallRuleDestinationType(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule destination type, Value: {self.obj} is not a list'


class InvalidFirewallRuleDestinationEmpty(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule destination, it cannot be empty list: {self.obj}'


class InvalidFirewallRuleIPAddress(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule IP address, Value: {self.obj} is not a valid CIDR IP'


class InvalidFirewallRulePort(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule port, Value: {self.obj}'


class InvalidFirewallRuleProtocol(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule protocol, Value: {self.obj}'


class InvalidFirewallRuleSingular(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        msg = f'Invalid firewall rule, Value: {self.obj}, When `any` or `@` is used Only one item is allowed per list'
        return msg


class InvalidFirewallRuleSource(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule source, Value: {self.obj}'


class InvalidFirewallRuleSourceType(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule source type, Value: {self.obj} is not a list'


class InvalidFirewallRuleSourceEmpty(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule source, it cannot be empty list: {self.obj}'


class InvalidFirewallRuleItem(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule, field: {self.obj} is missing in the rule object'


class InvalidFirewallRuleType(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule type, Value: {self.obj}'


class InvalidFirewallRuleVersion(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall rule version, Value: {self.obj}'


class InvalidSetElementsType(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid set elements type, Value: {self.obj} is not a list'


class InvalidSetElementsEmpty(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid set elements, it cannot be empty list: {self.obj}'


class InvalidSetItem(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid firewall set, field: {self.obj} is missing in the set object'


class InvalidSetName(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        msg = f'Invalid "name" field Value: {self.obj}, "name" is required. "name" can only contain  uppercase letters,'
        msg += ' lowercase letters, digits, a hypen (-) or an underscore (_) and the "name" must start with a letter.'
        return msg


class InvalidSetType(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        msg = f'Invalid type field: {self.obj},'
        msg += "The set type is not in 'ipv4_addr', 'ipv6_addr', 'inet_service'. and 'ether_addr'"
        return msg


class InvalidSetIPAddressVersion(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid IP Address version: {self.obj}, The element is not matching with set type'


class InvalidSetIPAddress(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid set element: {self.obj}, The element is not a valid CIDR IPAddress or IPNetwork'


class InvalidSetMacAddress(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid set element: {self.obj}, The element is not a valid Mac Address'


class InvalidSetPort(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid set element: {self.obj}, The element is not a valid Port'


class InvalidSetPortValue(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        msg = f'Invalid set element: {self.obj},'
        msg += "Port value can only be in the range 1-65536"
        return msg


class InvalidNATIface(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid iface field: {self.obj}, White spaces are not allowed in iface field'


class InvalidNATIPAddress(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid nat element: {self.obj}, The element is not a valid CIDR IPAddress or IPNetwork'


class InvalidNATIPAddressVersion(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid IP Address version: {self.obj}, NAT IPAddress version must be 4'


class InvalidNATItem(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid NAT, field: {self.obj} is missing in the NAT object'


class InvalidNATPrivate(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid NATs private field: {self.obj}, NAT private address is not RFC1918'


class InvalidNATPublic(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid NATs public field: {self.obj}, NAT public address cannot be RFC1918'


class InvalidKVMInterfaceItem(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid KVM Interface, field: {self.obj} is missing in the Interface object'


class InvalidKVMInterfaceMacAddress(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        return f'Invalid KVM Interface property mac_address: {self.obj}, The property is not a valid Mac Address'


class InvalidKVMInterfaceVlanBridge(BaseException):
    def __init__(self, obj):
        super().__init__(obj)
        self.obj = obj

    def __str__(self):
        msg = f'Invalid KVM Interface property vlan_bridge {self.obj} '
        msg += 'The "vlan_bridge" value must be of format `br1234`.'
        return msg
