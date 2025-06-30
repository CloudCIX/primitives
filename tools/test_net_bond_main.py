from cloudcix_primitives import net_bond_main
test_bond = {
        'name': 'mgmt0',
        'dhcp4': False,
        'dhcp6': False,
        'accept_ra': False,
        'interfaces': ['eno1', 'eno2'],
        'parameters': {
            'mode': '802.3ad',
        },
        'addresses': [
            '10.0.0.10/24',
            '2001:db8::10/64',
        ],
        'routes': [
            {'to': 'default', 'via': '10.254.3.205'},
            {'to': '2001:db8::/64', 'via': '2001:db8::1'},
        ],
    }

configured, error=net_bond_main.build(
    host='localhost',
    filename='011-mgmt0',
    standard_name='mgmt0',
    routes=test_bond['routes'],
    interfaces=test_bond['interfaces'],
    parameters=test_bond['parameters'],
    addresses=test_bond['addresses'],
    dhcp4=test_bond['dhcp4'],
    dhcp6=test_bond['dhcp6'],
    accept_ra=test_bond['accept_ra'],
)
print(f'Configured: {configured}, Error: {error}')
