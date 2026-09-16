# Network Printer Troubleshooting

## Printer Shows Offline
1. Confirm the printer's IP address hasn't changed — check DHCP reservation in the network admin console.
2. Ping the printer IP from the user's machine to confirm network reachability.
3. Remove and re-add the printer via Settings > Printers > Add Printer, using the IP found in step 1.

## Print Jobs Stuck in Queue
1. Open Print Queue, cancel all pending jobs.
2. Restart the Print Spooler service (services.msc > Print Spooler > Restart).
3. If jobs still stick, the print server (printserver01.corp.internal) may need a service restart — escalate to Infrastructure team.

## Requesting a New Printer for a Department
Submit via IT Admin Portal > Hardware Requests > Printer. Requires department head approval and budget code.
