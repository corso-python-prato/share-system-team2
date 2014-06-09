#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cmd
import socket
import struct
import json


class CommandParser(cmd.Cmd):
    """
    Command line interpreter
    Parse user input
    """

    DAEMON_HOST = 'localhost'
    DAEMON_PORT = 50001

    # Override attribute in cmd.Cmd
    prompt = '(PyBox)>>> '

    def send_to_daemon(self, message=None):
        """
        it sends user input command to the daemon server
        """
        if not message:
            return

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((self.DAEMON_HOST, self.DAEMON_PORT))

            lenght = struct.pack('!i', len(message))
            s.sendall(lenght)
            s.sendall(message)
            s.close()
            return True
        except socket.error:
            # log exception message
            print 'daemon is not running'
            return False

    def do_quit(self, line):
        """Exit Command"""
        return True

    def do_EOF(self, line):
        return True

    def do_newUser(self, line):  # fix it: use 'addUser'
        """ Create new User
            Usage: newUser <username> <password>
        """
        data = {}

        try:
            user, password = line.split()
            data['user'] = user
            data['pass'] = password
        except ValueError:
            print 'usage: newUser <username> <password>'
        else:
            message = {'newUser': data}
            self.send_to_daemon(json.dumps(message))

    def do_stop(self, line):
        message = {'stop_daemon': ''}
        self.send_to_daemon(json.dumps(message))


if __name__ == '__main__':
    CommandParser().cmdloop()
