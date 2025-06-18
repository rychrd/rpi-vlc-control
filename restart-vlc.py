#! /usr/bin/python3 env
# shutdown VLC and/or restart updated
import subprocess
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from socketserver import StreamRequestHandler, TCPServer
from functools import partial
from subprocess import Popen, run, PIPE



HOST = '192.168.0.198'
PORT = 54322
cmds = {b'shutdown\r\n', b'restart\r\n', b'playlist\n'}

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
            return False
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
            if line in cmds:
                send_cmd(line)

def send_cmd(command):
    conn = Connection((HOST, PORT))
    with conn as s:
        if s is False:
            raise ConnectionError
        else:
            reply = s.recv(64)# b''.join(iter(partial(s.recv, 8), b''))
            print(f'reply from initial request:\n{reply}')

            if reply.startswith(b'VLC'):
                print(f'VLC is listening - sending {command}\n')
                s.send(command)
                reply = b''.join(iter(partial(s.recv, 8), b''))
                print(f'VLC replied:\n{reply.decode('ascii')}')
                return True
    return

def restart_vlc():
    subprocess.run('cvlc --intf rc --rc-host 0.0.0.0:54322 --extraintf http --http-password xxxx --start-paused pList.m3u')


if __name__ == '__main__':
    serv = TCPServer(('localhost', 55550), IncomingHandler)
    serv.allow_reuse_address = 1

    while True:
        try:
            serv.serve_forever()
        except OSError as e:
            print(f'Exception in server loop {e}')

