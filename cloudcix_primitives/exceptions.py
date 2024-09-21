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
