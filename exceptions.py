def exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseException as e:
            return str(e)
    return wrapper


class CouldNotFindPodNets(BaseException):
    pass


class InvalidDNS(BaseException):
    pass


class InvalidFirewallRuleAction(BaseException):
    def __str__(self):
        return "Invalid firewall rule action."


class InvalidFirewallRuleDestination(BaseException):
    def __str__(self):
        return "Invalid firewall rule destination."


class InvalidFirewallRuleIPAddress(BaseException):
    def __str__(self):
        return "Invalid firewall rule IP address."


class InvalidFirewallRulePort(BaseException):
    def __str__(self):
        return "Invalid firewall rule port."


class InvalidFirewallRuleProtocol(BaseException):
    def __str__(self):
        return "Invalid firewall rule protocol."


class InvalidFirewallRuleSource(BaseException):
    def __str__(self):
        return "Invalid firewall rule source."


class InvalidFirewallRuleType(BaseException):
    def __str__(self):
        return "Invalid firewall rule type."


class InvalidFirewallRuleVersion(BaseException):
    def __str__(self):
        return "Invalid firewall rule version."


class InvalidPodNetMgmt(BaseException):
    pass


class InvalidPodNetOOB(BaseException):
    pass


class InvalidPodNetPublic(BaseException):
    pass


class InvalidPodNetPrivate(BaseException):
    pass


class InvalidPodNetIPv4CPE(BaseException):
    pass


class InvalidPodNetMgmtIPv6(BaseException):
    pass


class InvalidSetName(BaseException):
    def __str__(self):
        return "Invalid name field, white spaces are not allowed in name field."


class InvalidSetType(BaseException):
    def __str__(self):
        msg = "Invalid type field. "
        msg += "One of the set type is not in 'ipv4_addr', 'ipv6_addr', 'inet_service'. and 'ether_addr'"
        return msg


class InvalidSetIPAddressVersion(BaseException):
    def __str__(self):
        return "Invalid IP Address version, One of the element is not matching with set type."


class InvalidSetIPAddress(BaseException):
    def __str__(self):
        return "Invalid set element, One of the element is not a valid IPAddress."


class InvalidSetMacAddress(BaseException):
    def __str__(self):
        return "Invalid set element, One of the element is not a valid Mac Address."


class InvalidSetPort(BaseException):
    def __str__(self):
        return "Invalid set element, One of the element is not a valid Port."


class InvalidSetPortValue(BaseException):
    def __str__(self):
        msg = "Invalid set element, One of the element is not a valid Port."
        msg += "Port value can only be in the range 1-65536"
        return msg


class InvalidNATIface(BaseException):
    def __str__(self):
        return "Invalid iface field, white spaces are not allowed in iface field."


class InvalidNATIPAddress(BaseException):
    def __str__(self):
        return "Invalid nat element, One of the element is not a valid IPAddress."


class InvalidNATIPAddressVersion(BaseException):
    def __str__(self):
        return "Invalid IP Address version, NAT IPAddress version must be 4."


class InvalidNATPrivate(BaseException):
    def __str__(self):
        return "Invalid NATs private field, NAT private address is not RFC1918."


class InvalidNATPublic(BaseException):
    def __str__(self):
        return "Invalid NATs public field, NAT public address cannot be RFC1918."
