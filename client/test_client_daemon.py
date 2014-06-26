__author__ = 'milly'

import unittest
import client_daemon

server_timestamp = 1
files = {'ciao.txt': (3, 'md5md6'),
         'carlo.txt': (2, 'md6md6')}


class TestClientDaemon(unittest.TestCase):
    def setUp(self):
        self.client_daemon = client_daemon.Daemon()
        self.client_daemon.dir_state = {'timestamp': 0}
        self.client_daemon.client_snapshot = {'ciao.txt': (2, 'md5md5')}

    def test_sync_process(self):
        self.assertEqual(sorted(self.client_daemon._sync_process(server_timestamp, files)),
                         sorted([('download', 'ciao.txt'), ('download', 'carlo.txt')]))

if __name__ == '__main__':
    unittest.main()
