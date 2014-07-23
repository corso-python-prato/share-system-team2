#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cmd
import socket
import struct
import json
import getpass
import re


DAEMON_HOST = 'localhost'
DAEMON_PORT = 50001


def validate_email(address):
    """
    Validate an email address according to http://www.regular-expressions.info/email.html.
    :param address: str
    :return: bool
    """
    # WARNING: it seems a not 100%-exhaustive email address validation.
    # source: http://www.regular-expressions.info/email.html
    regexp = r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}\b'
    return bool(re.search(regexp, address, re.IGNORECASE))


def _getpass():
    """
    Ask the user for a new password. He must type it 2 times for confirmation.
    If successful, return the string of new password,
    else (empty or wrong confirmation) return False.
    """
    for attempt in range(3):
        new_password = getpass.getpass('Please enter a new password: ')
        if not new_password:
            # It empty, assume the user has changed mind
            print 'Aborted'
            return False
        new_password_confirmation = getpass.getpass('Please re-enter the new password: ')
        if new_password == new_password_confirmation:
            return new_password
        else:
            print 'Error: passwords doesn\'t match.'
    else:
        print 'No more attempts. '
        # The user have to re-enter the 'recoverpass' command to retry.
        return False


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

    def do_recoverpass(self, line):
        """
        Recover (= change, reset) the user's password.
        Usage: recoverpass <e-mail>
        """
        mail = line.strip()
        if not mail:
            print 'Bad arguments:'
            print 'usage: recoverpass <e-mail>'
            return False

        if not validate_email(mail):
            print 'Error: invalid email address.'
            return False
        else:
            req_message = {'reqrecoverpass': mail}
            r = self._send_to_daemon(req_message)
            if not r:
                print 'Error: the user does not exist or is not valid.'
                return False
            else:
                return True

    def do_changepass(self, line):
        """
        Enter the recover password code received by email.
        Usage: changepass <e-mail> <recoverpass_code>
        """
        try:
            mail, recoverpass_code = line.split()
        except ValueError:
            print 'Bad arguments:'
            print 'usage: changepass <e-mail> <recoverpass_code>'
            return False
        else:
            # Ask password without showing it:
            new_password = _getpass()
            if new_password:
                message = {'recoverpass': (mail, recoverpass_code, new_password)}
                resp = self._send_to_daemon(message)
                if not resp:
                    print 'Error: invalid recoverpass code.'
                    return False
                else:
                    return True
            else:
                # Empty password or confirm password not matching
                print 'Error: password not confirmed. Just recall the recoverpass command to retry.'
                return False


if __name__ == '__main__':
    CommandParser().cmdloop()


