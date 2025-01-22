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
