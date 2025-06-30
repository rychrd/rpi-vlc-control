#! /usr/bin/python3
# forwards various commands to VLC. Performs a shutdown or reboot of the Pi.
# Forwarding shutdown to VLC (port 54322) will just shutdown the player.

from socket import socket, gethostbyname, gethostname, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_KEEPALIVE
from socketserver import StreamRequestHandler, TCPServer
from functools import partial
from subprocess import run

VLC_HOST = gethostbyname(gethostname())
VLC_PORT = 54322

print(f'vlc ip: {VLC_HOST}\n')

vlc_cmds = [b'shutdown\r\n', b'playlist\r\n', b'play\r\n', b'frame\r\n', 'goto \r\n']
rpi_cmds = [b'pi_restart_vlc\n', b'pi_shutdown\n', b'pi_reboot\n']

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

        try:
            self.sock.connect(self.address)
        except ConnectionError as err:
            print(f'Socket was created but error connecting -  {err}')

        return self.sock

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, OSError ) :
            print(f'Exception handled in exit: {exc_type} {exc_val}')
            self.sock.close()
            return True
        self.sock.close()

class IncomingHandler(StreamRequestHandler):
    def handle(self):
        print(f'Got inbound connection from {self.client_address}')

        for line in self.rfile:
            print(f'received message {line}')

            if line.endswith(b'\r\n'):
                send_cmd(line)

            elif line in rpi_cmds:
                match line:
                    case b'pi_restart_vlc\n':
                        restart_vlc()
                    case b'pi_shutdown\n':
                        shutdown_PI()
                    case b'pi_reboot\n':
                        reboot_PI()
            else:
                 continue


def send_cmd(command):
    conn = Connection((VLC_HOST, VLC_PORT))
    with conn as s:
        if s is False:
            raise ConnectionError
        else:
            reply=b''.join(iter(partial(s.recv, 16), b'\n'))
            print(f'connected:\n{reply}')

            if reply.startswith(b'VLC'):
                print(f'----- VLC is running -----')
                reply= b''.join(iter(partial(s.recv, 1), b'>'))
                print(f'{reply}')
                s.sendall(command)
                reply = b''.join(iter(partial(s.recv,1), b'>'))
                print(f'VLC replied:\n{reply.decode("ascii")}')


def restart_vlc():
    run(['systemctl', '--user', 'restart', 'vlc-loader.service'])

def shutdown_PI():
    run(['sudo', 'shutdown', '-h', 'now'])

def reboot_PI():
    run(['sudo', 'shutdown', '-r', 'now'])


if __name__ == '__main__':

    serv = TCPServer(('0.0.0.0', 55550), IncomingHandler)
    serv.allow_reuse_address = 1
    print(f'TCP server created')

    with serv:
            serv.serve_forever()
