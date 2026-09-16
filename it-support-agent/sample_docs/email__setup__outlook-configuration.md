# Outlook Email Configuration

## New Employee Email Setup
1. Account is provisioned automatically within 24 hours of HR onboarding completion.
2. Server settings: IMAP server mail.corp.internal, port 993, SSL required.
3. Default mailbox quota is 50GB. Requests for increases go through IT Admin Portal > Storage Requests.

## Error: "Cannot Connect to Server" in Outlook
1. Confirm the user's account is active in Active Directory (not disabled/locked).
2. Check Outlook is on version 16.0.15000 or later — versions before this have a known TLS handshake bug with our mail server.
3. Have the user run Outlook in Safe Mode (hold Ctrl while launching) to rule out a corrupted add-in.

## Shared Mailbox Access Requests
Access to shared mailboxes requires manager approval submitted via the IT Admin Portal > Access Requests > Shared Mailbox form.
Turnaround is typically 1 business day.
