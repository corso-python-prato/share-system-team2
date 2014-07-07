#!/usr/bin/env python
# -*- coding: utf-8 -*-

import struct
import unittest

import client_cmdmanager


class FakeSocket(object):
    """
    Mock for socket:
    implements sendall and recv methods
    """
    def __init__(self):
        self.json_response = None
        self.sendall_size = None
        self.recv_size = None

    def set_response(self, response):
        self.json_response = ''.join(['{"message": "', response, '" }'])

    def sendall(self, message):
        if not self.sendall_size:
            self.sendall_size = int(struct.unpack('!i', message)[0])
        else:
            assert self.sendall_size == len(message)
            self.sendall_size =None

    def recv(self, bytes):
        if not self.recv_size:
            self.recv_size = len(self.json_response)
            return struct.pack('!i', len(self.json_response))
        else:
            self.recv_size = None
            return self.json_response


class TestCmdManagerDaemonConnection(unittest.TestCase):
    """
    Test the connection between Cmd Manager and Daemon
    """
    def setUp(self):
        self.commandparser = client_cmdmanager.CommandParser()
        self.commandparser.sock = FakeSocket()

    def test_sent_to_daemon_input(self):
        """
        Tests the string passed in input:
        test a long string
        """
        response = 'ciao sono test'
        self.commandparser.sock.set_response(response)
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
        self.commandparser.sock.set_response(response)

        self.assertEquals(self.commandparser._send_to_daemon(input_str), response)

        response = response * 100000
        self.commandparser.sock.set_response(response)

        self.assertEquals(self.commandparser._send_to_daemon(input_str), response)


class TestDoQuitDoEOF(unittest.TestCase):
    """
    Test do_quit method
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