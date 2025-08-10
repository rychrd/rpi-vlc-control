#! /usr/bin/python3
# forwards various commands to VLC. Performs a shutdown or reboot of the Pi.
# Forwarding shutdown to VLC (port 54322) will just shut down the player.

from socket import socket, gethostbyname, gethostname, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from socketserver import StreamRequestHandler, TCPServer, BaseRequestHandler, UDPServer
from functools import partial
from subprocess import run
import threading

VLC_HOST = gethostbyname(gethostname())
VLC_PORT = 54322

print(f'vlc ip: {VLC_HOST}\n')


class Connection:
    def __init__(self, addr_prt, timeout=2, family=AF_INET, transport=SOCK_STREAM):
        self.address = addr_prt
        self.family = family
        self.type = transport
        self.timeout = timeout
        self.sock = None

    def __enter__(self):
        if self.sock is not None:
            raise RuntimeError('Connection already set up')
        self.sock = socket(self.family, self.type)
        self.sock.settimeout(self.timeout)
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

        self.sock.connect(self.address)

        return self.sock

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, OSError):
            print(f'Exception handled in exit: {exc_type} {exc_val}')
            self.sock.close()
            return True
        self.sock.close()
        return None

class CommandDispatcher:
    def __init__(self):
        self.rpi_commands_map = {
            b'pi_restart_vlc\n': 'pi_restart_vlc',
            b'pi_shutdown\n': 'pi_shutdown',
            b'pi_reboot\n': 'pi_reboot',
        }

    def process_command(self, data):
        if data.endswith(b'\r\n'):
            self.forward_to_vlc(data)
        else:
            rpi_command = self.rpi_commands_map.get(data)
            if rpi_command:
                cmd = getattr(self, rpi_command)
                cmd()

    def pi_restart_vlc(self):
        print(f'CALLED VLC RESTART IN THE CLASS')
        # run(['systemctl', '--user', 'restart', 'vlc-loader.service'])

    def pi_shutdown(self):
        run(['sudo', 'shutdown', '-h', 'now'])

    def pi_reboot(self):
        run(['sudo', 'shutdown', '-r', 'now'])

    def forward_to_vlc(self, command):
        conn = Connection((VLC_HOST, VLC_PORT))
        try:
            with conn as s:
                reply = b''.join(iter(partial(s.recv, 1), b'\n'))
                print(f'connected:\n{reply}')

                if reply.startswith(b'VLC'):
                    print(f'----- VLC is running -----')
                    reply = b''.join(iter(partial(s.recv, 1), b'>'))
                    print(f'{reply}')
                    s.sendall(command)
                    reply = b''.join(iter(partial(s.recv, 1), b'>'))
                    print(f'VLC replied:\n{reply.decode("ascii")}')

        except (ConnectionRefusedError,
                ConnectionError,
                TimeoutError) as e:
            print(f"Couldn't connect to VLC: {e}")
        except Exception as e:
            print(f'Unexpected error occurred {e}')


class TcpMessageHandler(StreamRequestHandler):
    def handle(self):
        print(f'Got inbound connection from {self.client_address}')
        message_handler = CommandDispatcher()

        for line in self.rfile:
            print(f'received message {line}')
            message_handler.process_command(line)

class UdpMessageHandler(BaseRequestHandler):
    def handle(self):
        message = self.request[0]
        sender = self.client_address
        print(f'Got UDP datagram {message} from {sender}')
        message_handler = CommandDispatcher()
        message_handler.process_command(message)

def start_tcp_server(address):
    """Wrap the start of the server here so it's still possible to use a context manager and exceptions"""
    try:
        with TCPServer(address, TcpMessageHandler) as tcp_server:
            tcp_server.allow_reuse_address = True
            print(f'TCP Server listening on {address}')
            tcp_server.serve_forever()
    except Exception as e:
        print(f'TCP thread crashed: {e}:')
    finally:
        print(f'Closed TCP thread')

def start_udp_server(address):
    try:
        with UDPServer(address, UdpMessageHandler) as udp_server:
            udp_server.serve_forever()
    except Exception as e:
        print(f'UDP thread crashed: {e}:')
    finally:
        print(f'Closed UDP thread')

if __name__ == '__main__':

    tcp_serv = TCPServer(('0.0.0.0', 55550), TcpMessageHandler)
    tcp_serv.allow_reuse_address = True
    print(f'TCP server created')
    udp_server = UDPServer(('0.0.0.0', 55551), UdpMessageHandler)
    print(f'UDP server created')



