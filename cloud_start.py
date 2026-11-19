"""Production entry point. Owner credentials must be supplied as host secrets."""
import os
import sys
import uvicorn
from accounts import create_owner, owner_exists

if __name__ == '__main__':
    if not owner_exists():
        username = os.environ.get('OWNER_USERNAME', '').strip()
        password = os.environ.get('OWNER_PASSWORD', '')
        if not username or not password:
            sys.exit('Provide OWNER_USERNAME and OWNER_PASSWORD environment variables on the host before first deployment.')
        create_owner(username, password)
        print('Owner account initialized in persistent storage.')
    uvicorn.run('app:app', host='0.0.0.0', port=int(os.environ.get('PORT', '10000')), workers=1,
                proxy_headers=True, forwarded_allow_ips='*')
