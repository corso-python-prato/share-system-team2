#!/usr/bin/env python
#-*- coding: utf-8 -*-

import cmd
import requests


class CommandParser(cmd.Cmd):
    """Command line interpeter
    Parse user input"""

    prompt = '(Share)>>>'

    def do_google(self, line):
    """Print Google sourcepage"""
        r = requests.get("http://www.google.it")
        print r.text

    def do_quit(self, line):
    """Exit Command"""
        return True

    def do_EOF(self, line):
        return True


if __name__ == '__main__':
    CommandParser().cmdloop()