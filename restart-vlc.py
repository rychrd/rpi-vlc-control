#! /usr/bin/python3
# forwards various commands to VLC. Performs a shutdown or reboot of the Pi.
# Forwarding shutdown to VLC (port 54322) will just shut down the player.

from socket import socket, gethostbyname, gethostname, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from socketserver import StreamRequestHandler, TCPServer
from functools import partial
from subprocess import run

VLC_HOST = gethostbyname(gethostname())
VLC_PORT = 54322

print(f'vlc ip: {VLC_HOST}\n')
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

        self.sock.connect(self.address)

        return self.sock

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, OSError ) :
            print(f'Exception handled in exit: {exc_type} {exc_val}')
            self.sock.close()
            return True
        self.sock.close()
        return None


class IncomingHandler(StreamRequestHandler):
    rpi_commands_map = {
        b'pi_restart_vlc\n': 'pi_restart_vlc',
        b'pi_shutdown\n': 'pi_shutdown',
        b'pi_reboot\n': 'pi_reboot',
    }

    def handle(self):
        print(f'Got inbound connection from {self.client_address}')

        for line in self.rfile:
            print(f'received message {line}')
            if line.endswith(b'\r\n'):
                self.send_cmd(line)
            else:
                rpi_command = self.rpi_commands_map.get(line)
                if rpi_command:
                    cmd = getattr(self, rpi_command)
                    cmd()
                else:
                    continue

    def pi_restart_vlc(self):
        print(f'CALLED RESTART IN THE CLASS')
        run(['systemctl', '--user', 'restart', 'vlc-loader.service'])

    def pi_shutdown(self):
        run(['sudo', 'shutdown', '-h', 'now'])

    def pi_reboot(self):
        run(['sudo', 'shutdown', '-r', 'now'])

    def send_cmd(self, command):
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

if __name__ == '__main__':

    serv = TCPServer(('0.0.0.0', 55550), IncomingHandler)
    serv.allow_reuse_address = True
    print(f'TCP server created')

    with serv:
            serv.serve_forever()
