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
    pass


class InvalidFirewallRuleDestination(BaseException):
    pass


class InvalidFirewallRuleIPAddress(BaseException):
    pass


class InvalidFirewallRulePort(BaseException):
    pass


class InvalidFirewallRuleProtocol(BaseException):
    pass


class InvalidFirewallRuleSource(BaseException):
    pass


class InvalidFirewallRuleType(BaseException):
    pass


class InvalidFirewallRuleVersion(BaseException):
    pass


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
