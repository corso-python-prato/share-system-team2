#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import json

import client_cmdmanager
import test_utils


class CmdParserMock(client_cmdmanager.CommandParser):
    """
    Mock method _send_to_daemon with fixed return value, set by passing it to the constructor.
    """
    def __init__(self, daemon_return_value=None):
        client_cmdmanager.CommandParser.__init__(self)  # old style class
        self.daemon_return_value = daemon_return_value

    def _send_to_daemon(self, message=None):
        return self.daemon_return_value


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

        response = response * 100000
        self.commandparser.sock.set_response(json.dumps({'message': response}))

        self.assertEquals(self.commandparser._send_to_daemon(input_str), response)


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


class TestRecoverpassCommand(unittest.TestCase):
    """
    Test 'recoverpass' command.
    """
    def setUp(self):
        self.commandparser = CmdParserMock()

    def test_recoverpass_empty_email(self):
        r = self.commandparser.do_recoverpass('')
        self.assertFalse(r)

    def test_recoverpass_no_at_email(self):
        r = self.commandparser.do_recoverpass('invalid.mail')
        self.assertFalse(r)

    def test_recoverpass_valid_mail(self):
        self.commandparser.daemon_return_value = 'Ok'
        r = self.commandparser.do_recoverpass('myemail@gmail.com')
        self.assertTrue(r)

    def test_recoverpass_2_words(self):
        r = self.commandparser.do_recoverpass('myemail@gmail.com altroargomento')
        self.assertFalse(r)


class TestChangepassCommand(unittest.TestCase):
    """
    Test 'changepass' command.
    """
    def setUp(self):
        self.valid_line = 'pippo.topolinia@gmail.com my_recoverpass_code'
        self.commandparser = CmdParserMock()

    def test_bad_args(self):
        r = self.commandparser.do_changepass('')
        self.assertFalse(r)

        r = self.commandparser.do_changepass('myemail@gmail.com')
        self.assertFalse(r)

        r = self.commandparser.do_changepass('myemail@gmail.com activationcode extra-arg')
        self.assertFalse(r)

    def test_password_unconfirmed(self):
        """
        If the new password is not confirmed, the command must fail.
        """
        client_cmdmanager._getpass = lambda: False
        r = self.commandparser.do_changepass(self.valid_line)
        self.assertFalse(r)  # because _getpass fail (return False)

    def test_invalid_code(self):
        client_cmdmanager._getpass = lambda: 'mynewpassword'
        # Assuming that a empty daemon return value means that the token is invalid.
        self.commandparser.daemon_return_value = ''
        r = self.commandparser.do_changepass(self.valid_line)
        self.assertFalse(r)

    def test_ok(self):
        # mock client_cmdmanager._getpass function
        client_cmdmanager._getpass = lambda: 'mynewpassword'
        self.commandparser.daemon_return_value = 'Password changed succesfully'
        r = self.commandparser.do_changepass(self.valid_line)
        self.assertTrue(r)


if __name__ == '__main__':
    unittest.main()
