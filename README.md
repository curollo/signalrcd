# signalrcd

Quick and dirty solution to bridge your Signal client with IRC. Requires signal-cli for connectivity with Signal servers.

## Usage:

1) Link account with signal-cli and run in daemon mode with provided dbus interface.

   https://github.com/AsamK/signal-cli/wiki/DBus-service

2) Run this script and connect to spawned irc daemon (default: localhost/6999)

3) Try to /msg your Signal contact.
