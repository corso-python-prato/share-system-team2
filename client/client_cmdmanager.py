#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cmd
import socket
import struct
import json
import os


# The path for configuration directory and daemon configuration file
CONFIG_DIR = os.path.join(os.environ['HOME'], '.PyBox')
CONFIG_FILEPATH = os.path.join(CONFIG_DIR, 'daemon_config')
# Default configuration for socket
daemon_host = 'localhost'
daemon_port = 50001


def load_cfg(cfg_path=CONFIG_FILEPATH):
    """
    Load config file with socket configuration
    :param cfg_path: filepath of cfg file
    :return:
    """
    try:
        with open(cfg_path, 'r') as fo:
            loaded_config = json.load(fo)
    except (ValueError, IOError, OSError):
        pass
    else:
        try:
            global daemon_host
            daemon_host = loaded_config['cmd_address']
            global daemon_port
            daemon_port = loaded_config['cmd_port']
            return
        except KeyError:
            pass
    # If all go right i will not do this print
    print 'Impossible to load cfg, client_daemon already loaded?'
    print 'Loaded default configuration for socket'


class CommandParser(cmd.Cmd):
    """
    Command line interpreter
    Parse user input
    """

    # Override attribute in cmd.Cmd
    prompt = '(PyBox)>>> '

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def _send_to_daemon(self, message=None):
        """
        it sends user input command to the daemon server
        """
        if not message:
            raise

        data_packet = json.dumps(message)
        try:
            # send the command to daemon
            data_packet_size = struct.pack('!i', len(data_packet))
            self.sock.sendall(data_packet_size)
            self.sock.sendall(data_packet)

            # receive the information message from daemon
            response_size = self.sock.recv(struct.calcsize('!i'))
            if len(response_size) == struct.calcsize('!i'):
                response_size = int(struct.unpack('!i', response_size)[0])
                response_packet = ''
                remaining_size = response_size
                while len(response_packet) < response_size:
                    response_buffer = self.sock.recv(remaining_size)
                    remaining_size -= len(response_buffer)
                    response_packet = ''.join([response_packet, response_buffer])

                response = json.loads(response_packet)
                return response['message']
            else:
                raise Exception('Error: lost connection with daemon')

        except socket.error as ex:
            # log exception message
            print 'Socket Error: ', ex

    def preloop(self):
        """
        setup before the looping start
        """
        self.sock.connect((daemon_host, daemon_port))

    def postloop(self):
        """
        Closures when looping stop
        """
        self.sock.close()

    def do_quit(self, line):
        """Exit Command"""
        return True

    def do_EOF(self, line):
        return True

    def do_shutdown(self, line):
        """
        Shutdown the daemon
        """
        message = {'shutdown': ()}
        self._send_to_daemon(message)

    def do_register(self, line):
        """
        Create new user:
        Send a request to server for creating a new user
        Usage: register <e-mail> <password>
        """
        try:
            mail, password = line.split()
        except ValueError:
            print 'Bad arguments:'
            print 'usage: register <e-mail> <password>'
        else:
            message = {'register': (mail, password)}
            response = self._send_to_daemon(message)
            if 'improvements' in response:
                print '\nThe password you entered is weak, possible improvements:'
                for k, v in response['improvements'].items():
                    print '{}: {}'.format(k, v)
            else:
                print response['content']

    def do_activate(self, line):
        """
        Activate the user:
        Send the token (received by mail) to server for activating the new user
        Usage: activate <e-mail> <token>
        """
        try:
            mail, token = line.split()
        except ValueError:
            print 'Bad arguments:'
            print 'usage: activate <e-mail> <token>'
        else:
            message = {'activate': (mail, token)}
            response = self._send_to_daemon(message)
            print response


if __name__ == '__main__':
    load_cfg()
    CommandParser().cmdloop()
