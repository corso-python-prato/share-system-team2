#!/usr/bin/env python
#-*- coding: utf-8 -*-

import cmd
import socket
import struct
import json

DEAMON_HOST = 'localhost'
DEAMON_PORT = 50001


def send_to_deamon(message=None):
    if not message:
        return

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((DEAMON_HOST, DEAMON_PORT))

    lenght = struct.pack('!i', len(message))
    s.sendall(lenght)
    s.sendall(message)
    s.close()


class CommandParser(cmd.Cmd):
    """Command line interpreter
    Parse user input"""

    prompt = '(Share)>>>'

    def do_quit(self, line):
        """Exit Command"""
        return True

    def do_EOF(self, line):
        return True

    def do_newUser(self, line):
        """ Create new User
            Usage: newUser <username> <password>
        """
        data = {}

        try:
            user, password = line.split()
            data['user'] = user
            data['pass'] = password
        except ValueError:
            print 'bad arguments'
        else:
            cmd = {"newUser": data}
            send_to_deamon(json.dumps(cmd))



if __name__ == '__main__':
    CommandParser().cmdloop()


