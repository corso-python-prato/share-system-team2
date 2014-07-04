#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cmd
import socket
import struct
import json


DAEMON_HOST = 'localhost'
DAEMON_PORT = 50001


class CommandParser(cmd.Cmd):
    """
    Command line interpreter
    Parse user input
    """

    # Override attribute in cmd.Cmd
    prompt = '(PyBox)>>> '

    def _send_to_daemon(self, message=None):
        """
        it sends user input command to the daemon server
        """
        if not message:
            raise

        data_packet = json.dumps(message)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((DAEMON_HOST, DAEMON_PORT))

            # send the command to daemon
            data_packet_size = struct.pack('!i', len(data_packet))
            s.sendall(data_packet_size)
            s.sendall(data_packet)

            # receive the information message from daemon
            response_size = s.recv(struct.calcsize('!i'))
            if len(response_size) == struct.calcsize('!i'):
                response_size = int(struct.unpack('!i', response_size)[0])
                response_packet = ''
                remaining_size = response_size
                while len(response_packet) < response_size:
                    response_buffer = s.recv(remaining_size)
                    remaining_size -= len(response_buffer)
                    response_packet = ''.join([response_packet, response_buffer])

                response = json.loads(response_packet)

                print response['message']
            else:
                raise Exception('Error: lost connection with daemon')

            s.close()
        except socket.error as ex:
            # log exception message
            print 'Socket Error: ', ex

    def do_quit(self, line):
        """Exit Command"""
        return True

    def do_EOF(self, line):
        return True

    def do_reguser(self, line):
        """ Create new user
            Usage: reguser <username> <password>
        """

        try:
            user, password = line.split()
        except ValueError:
            print 'usage: newUser <username> <password>'
        else:
            message = {'reguser': (user, password)}
            print message
            self._send_to_daemon(message)

    def do_shutdown(self, line):
        message = {'shutdown': ()}
        self._send_to_daemon(message)


if __name__ == '__main__':
    CommandParser().cmdloop()
