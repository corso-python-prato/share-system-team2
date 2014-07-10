__author__ = 'milly'

import struct


class FakeSocket(object):
    """
    Mock for socket:
    implements sendall and recv methods
    """
    def __init__(self):
        self.response = None
        self.sendall_size = None
        self.recv_size = None

    def set_response(self, response):
        """
        Set the response message to send during the recv call
        """
        self.response = response

    def sendall(self, message):
        """
        Assert data consistence: it check it recv
        """
        if not self.sendall_size:
            self.sendall_size = int(struct.unpack('!i', message)[0])
        else:
            assert self.sendall_size == len(message)
            self.sendall_size = None

    def recv(self, bytes):
        if not self.recv_size:
            self.recv_size = len(self.response)
            return struct.pack('!i', len(self.response))
        else:
            self.recv_size = None
            return self.response