#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import unittest
import string
import random

import client_cmdmanager


def id_gen(size=int(random.random() * 8), chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class Testcmdmanager(unittest.TestCase):
    def setUp(self):
        self.CommandParser = client_cmdmanager.CommandParser()
        self.random_strings = []
        for num in range(10):
            self.random_strings.append(id_gen() + id_gen() + ' ' + id_gen() + '   ' + id_gen() + ' ' + id_gen())

    def tearDown(self):
        pass

    def test_do_quit(self):
        """
        Verify do_quit generate always True with random string
        """
        for string in self.random_strings:
            self.assertTrue(self.CommandParser.do_quit(string))

    def test_do_EOF(self):
        """
        Verify do_EOF generate always True with random string
        """
        for string in self.random_strings:
            self.assertTrue(self.CommandParser.do_EOF(string))

    def test_failed_connection(self):
            self.assertRaises(socket.error, self.CommandParser.do_newUser, 'user pass') is False


if __name__ == '__main__':
    unittest.main()
