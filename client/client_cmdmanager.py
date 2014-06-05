#!/usr/bin/env python
#-*- coding: utf-8 -*-

import cmd
# import requests
import fake_request as requests

class CommandParser(cmd.Cmd):
    """Command line interpreter
    Parse user input"""

    prompt = '(Share)>>>'

    def do_google(self, line):
        """Print Google source page"""
        r = requests.get("http://www.google.it")
        print r.text

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
            r = requests.post('NEWUSER', data)
            try:
                r.raise_for_status()
            except: # (work in progess) must catch specific exception
                print r.reason


if __name__ == '__main__':
	print 'hello world'
    CommandParser().cmdloop()


