#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cmd
import socket
import struct
import json
import getpass
import re
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

    def postcmd(self, stop, line):
        """
        This function is called after any do_<something>.
        If the last operation called return 'exit' the program will be closed
        :param stop: Is the returning value of the last cmd executed
        :param line: Is the last line received from the last cmd executed
        :return:
        """
        if stop == 'exit':
            return True

    def do_quit(self, line):
        """Exit Command"""
        return 'exit'

    def do_EOF(self, line):
        return 'exit'

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
            # for testing purpose
            return False
        else:
            message = {'register': (mail, password)}
            response = self._send_to_daemon(message)
            if 'improvements' in response:
                print '\nThe password you entered is weak, possible improvements:'
                for k, v in response['improvements'].items():
                    print '{}: {}'.format(k, v)
            else:
                print response['content']
            # for testing purpose
            return response

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
            # for testing purpose
            return False
        else:
            message = {'activate': (mail, token)}
            response = self._send_to_daemon(message)
            print response
            return response

    def do_recoverpass(self, line):
        """
        This command allows you to recover (i.e. change) a lost password,
        in 2 steps:
            1st step: (PyBox)>>> recoverpass <e-mail>
            (wait for the email containing the <recoverpass_code>)
            2nd step: (PyBox)>>> recoverpass <e-mail> <recoverpass_code>
        """
        args = line.split()
        if not args:
            print 'Bad arguments:'
            print 'usage: recoverpass <e-mail> [<recoverpass_code>]'
            return False
        else:
            mail = args[0]
            # must be a valid email
            if not validate_email(mail):
                print 'Error: invalid e-mail address.'
                return False

            if len(args) == 1:
                req_message = {'reqrecoverpass': mail}
                r = self._send_to_daemon(req_message)
                if not r:
                    print 'Error: the user does not exist or is not valid.'
                    return False
                print 'Recover password email sent to {}, check your inbox!'.format(mail)
                return True
            elif len(args) == 2:
                # The command used with 2 parameters allow the user to enter the "recoverpass code"
                # received by email and actually change the password.
                # Usage: changepass <e-mail> <recoverpass_code>
                recoverpass_code = args[1]

                # Ask password without showing it:
                new_password = _getpass()
                if new_password:
                    message = {'recoverpass': (mail, recoverpass_code, new_password)}
                    resp = self._send_to_daemon(message)
                    if not resp:
                        print 'Error: invalid recoverpass code.'
                        return False
                    else:
                        print 'OK. Password changed successfully!'
                        return True
                else:
                    # Empty password or confirm password not matching
                    print 'Error: password not confirmed. Just recall the recoverpass command to retry.'
                    return False
            else:
                print 'Bad arguments:'
                print 'usage: recoverpass <e-mail>  [<recoverpass_code>]'
                return False


if __name__ == '__main__':
    load_cfg()
    CommandParser().cmdloop()
