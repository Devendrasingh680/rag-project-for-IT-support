# VPN Connection Troubleshooting

## Error: "VPN Connection Timed Out"
This usually means the client cannot reach the VPN gateway.
Steps:
1. Confirm the user is connected to the internet (open a browser, load any page).
2. Check that the VPN client is version 4.2 or later — older versions do not support the current gateway certificate.
3. Have the user restart the VPN client service: Settings > Network > VPN Client > Restart Service.
4. If the issue persists, check the internal status page at status.corp.internal for a gateway outage.

## Error: "Authentication Failed" on VPN Login
1. Confirm the user's AD password has not expired (Active Directory > Users > check "Password Expires" field).
2. If using MFA, confirm the authenticator app time is synced (clock drift over 30 seconds causes token rejection).
3. Reset the VPN-specific credential cache: `vpnclient --clear-cache` from an admin terminal.

## Split Tunneling Configuration
Split tunneling is enabled by default for all Sales and Marketing roles as of Q2 policy update.
Engineering roles use full-tunnel by default for security compliance.
To change: IT Admin Portal > VPN Policies > select role > toggle Split Tunnel.
