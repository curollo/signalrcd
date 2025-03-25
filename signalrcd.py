#!/usr/bin/env python3

import asyncio
import socket
from dbus_next.aio import MessageBus
from dbus_next import BusType, Variant

ircd = "signalrcd.local"
signal_nick_map = dict(sample_nick="+99999999999")

async def handle_signal_message(message_interface, writer, nickname):
    def on_message(timestamp, source, group_id, message, attachments):
        print(f"Message from {source}: {message}")
        asyncio.create_task(
            process_signal_message(source, message, message_interface, writer, nickname)
        )

    return on_message


async def process_signal_message(source, message, signal_interface, writer, nickname):
    try:
        get_name_reply = await signal_interface.call_get_contact_name(source)
        name = get_name_reply.body[0] if get_name_reply else None
    except Exception as e:
        print(f"Error getting contact name: {e}")
        name = None

    fromnick = name.replace(" ", "_").replace(":", "") if name else source
    if fromnick not in signal_nick_map:
        signal_nick_map[fromnick] = source

    irc_msg = f":{fromnick}!signal@{ircd} PRIVMSG {nickname} :{message}\r\n"
    writer.write(irc_msg.encode())
    await writer.drain()


async def handle_client(reader, writer):
    nickname = None
    # Get nickname from handshake
    while 1:
        data = await reader.read(512)
        if not data:
            break
        handshake = data.decode("utf-8", errors="ignore")
        if "NICK " in handshake:
            nickname = handshake.split("NICK ")[1].split("\r\n")[0].strip()
            break

    if not nickname:
        writer.close()
        await writer.wait_closed()
        return

    # Send motd
    def motd(action, message):
        writer.write(f":{ircd} {action} {nickname} :{message}\r\n".encode())

    motd("001", "Bridge ready")
    await writer.drain()

    # Setup D-Bus Signal interface
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    introspection = await bus.introspect("org.asamk.Signal", "/org/asamk/Signal")
    signal_obj = bus.get_proxy_object(
        "org.asamk.Signal", "/org/asamk/Signal", introspection
    )
    signal = signal_obj.get_interface("org.asamk.Signal")

    # Listen for messages
    signal.on_message_received(await handle_signal_message(signal, writer, nickname))

    # Process client commands
    while 1:
        try:
            line = (await reader.readuntil(b"\r\n")).decode().strip()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            break

        if line.startswith("PING "):
            challenge = line.split(" ", 1)[1]
            irc("PONG", challenge)
            print(f"Ping-Pong: {challenge}")
        elif line.startswith("PRIVMSG "):
            parts = line.split(" ", 2)
            recipient = parts[1]
            msg_content = parts[2].split(":", 1)[1] if ":" in parts[2] else parts[2]
            number = signal_nick_map.get(recipient, recipient)
            try:
                await signal.call_send_message(msg_content, [], [number])
                print(f"Sent to {number}: {msg_content}")
            except Exception as e:
                print(f"Error sending message: {e}")
        else:
            irc("421", "Unknown command")
            print(f"Unhandled command: {line}")

        await writer.drain()

    writer.close()
    await writer.wait_closed()


async def main():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 6999)
    print("Listening on 127.0.0.1:6999...")
    async with server:
        await server.serve_forever()


asyncio.run(main())
