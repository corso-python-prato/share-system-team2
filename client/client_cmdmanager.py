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

    def _send_to_daemon(self, message=None):
        """
        it sends user input command to the daemon server
        """
        if not message:
            return

        message = json.dumps(message)

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

    def do_newUser(self, line):
        """ Create new User
            Usage: newUser <username> <password>
        """

        try:
            user, password = line.split()
        except ValueError:
            print 'usage: newUser <username> <password>'
        else:
            message = {'newUser': (user, password)}
            print message
            self._send_to_daemon(message)

    def do_shutdown(self, line):
        message = {'shutdown': ()}
        self._send_to_daemon(message)


if __name__ == '__main__':
    CommandParser().cmdloop()
