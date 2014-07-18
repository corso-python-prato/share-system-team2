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

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def _send_to_daemon(self, message=None, show=True):
        """
        it sends user input command to the daemon server
        if show = True then print response message, otherwise it get message response without printing it
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

                if show:
                    print response['message']

                # to improve testing
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
        self.sock.connect((DAEMON_HOST, DAEMON_PORT))

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
            self._send_to_daemon(message)

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
            self._send_to_daemon(message)

    def do_addshare(self, line):
        """
        Share a folder with a new user
        Usage: addshare <shared_folder> <user>
        """
        try:
            shared_folder, user = line.split()
        except ValueError:
            print 'Bad arguments:'
            print 'usage: share <share_folder> <user>'
        else:
            sharing_path = self._send_to_daemon({'daemon_config': 'sharing_path'}, False)
            if not os.path.exists(''.join([sharing_path, os.sep, shared_folder])):
                print '"%s" not exists' % shared_folder
            else:
                message = {'addshare': (shared_folder, user)}
                self._send_to_daemon(message)


if __name__ == '__main__':
    CommandParser().cmdloop()


