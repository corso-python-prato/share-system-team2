#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import json

import client_cmdmanager
import test_utils


# Test-user account details
USR, PW = 'mail@hotmail.com', 'Hard_Password_Since_1985'


class TestCmdManagerDaemonConnection(unittest.TestCase):
    """
    Test the connection between Cmd Manager and Daemon
    """
    def setUp(self):
        self.commandparser = client_cmdmanager.CommandParser()
        self.commandparser.sock = test_utils.FakeSocket()

    def test_sent_to_daemon_input(self):
        """
        Tests the string passed in input:
        test a long string
        """
        response = 'ciao sono test'
        self.commandparser.sock.set_response(json.dumps({'message': response}))
        input_str = 'input'

        self.assertEquals(self.commandparser._send_to_daemon(input_str), response)
        self.assertEquals(self.commandparser._send_to_daemon(input_str * 100000), response)

    def test_send_to_daemon_output(self):
        """
        Tests the string received:
        test a long string
        """
        input_str = 'input'
        response = 'ciao sono test'
        self.commandparser.sock.set_response(json.dumps({'message': response}))

        self.assertEquals(self.commandparser._send_to_daemon(input_str), response)

        self.commandparser.sock.set_response(json.dumps({'message': response * 100000}))

        self.assertEquals(self.commandparser._send_to_daemon(input_str), response * 100000)


class TestDoQuitDoEOF(unittest.TestCase):
    """
    Test do_quit and EOF method
    """
    def setUp(self):
        self.commandparser = client_cmdmanager.CommandParser()
        self.line = 'linelinelineline'

    def test_do_quit(self):
        """
        Verify do_quit
        """
        self.assertTrue(self.commandparser.do_quit(self.line))

    def test_do_EOF(self):
        """
        Verify do_EOF
        """
        self.assertTrue(self.commandparser.do_EOF(self.line))


if __name__ == '__main__':
    unittest.main()
