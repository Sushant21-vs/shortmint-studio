"""Run on the computer that hosts ShortMint, BEFORE accepting friend registrations."""
from getpass import getpass
from accounts import create_owner, owner_exists

if owner_exists():
    print('Owner account is already configured. No changes made.')
else:
    print('\n=== ShortMint Studio owner setup ===')
    print('You are creating the UNLIMITED-CREDITS admin account.')
    print('Your password will not be displayed while typing.')
    while True:
        name = input('Owner username (3-24 letters/numbers): ').strip()
        pwd = getpass('Owner password (at least 10 characters): ')
        confirm = getpass('Confirm password: ')
        if pwd != confirm:
            print('Passwords do not match. Please try again.\n')
            continue
        try:
            create_owner(name, pwd)
            print('\nOwner created successfully. Log in with your username/password.\n')
            break
        except ValueError as exc:
            print(str(exc) + '\n')
