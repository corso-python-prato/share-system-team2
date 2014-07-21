#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cmd
import socket
import struct
import json
import getpass


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

    def do_changepass(self, line):
        """
        Change user password.
        Usage: changepass <e-mail>
        """
        mail = line.strip()

        for attempt in range(3):
            new_password = getpass.getpass('Please enter new password: ')
            if not new_password:
                # It empty, assume the user has changed mind
                print 'Aborted'
                return
            new_password_confirmation = getpass.getpass('Please re-enter new password: ')
            if new_password == new_password_confirmation:
                req_message = {'reqchangepass': mail}
                self._send_to_daemon(req_message)

                # Wait for the email containing the reset code...

                reset_code = raw_input('Enter the reset password code received by email: ')
                message = {'changepass': (mail, reset_code, new_password)}
                self._send_to_daemon(message)
                break  # exit from trial for
            else:
                print 'Error: passwords doesn\'t match.'
        else:
            print 'No more attempts. Just recall the changepass command to retry.'
            # The user have to re-enter the 'changepass' command to retry.


if __name__ == '__main__':
    CommandParser().cmdloop()


