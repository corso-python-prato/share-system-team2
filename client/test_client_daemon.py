import hashlib
import unittest
import os
import shutil
import json
import time
import random

import httpretty
import client_daemon

TEST_DIR = os.path.join(os.environ['HOME'], 'daemon_test')
CONFIG_DIR = os.path.join(TEST_DIR, '.PyBox')
CONFIG_FILEPATH = os.path.join(CONFIG_DIR, 'daemon_config')
LOCAL_DIR_STATE_FOR_TEST = os.path.join(CONFIG_DIR, 'test_local_dir_state')

TEST_SHARING_FOLDER = os.path.join(TEST_DIR, 'test_sharing_folder')

LIST_OF_TEST_FILES = [
    'file1.txt',
    'file2.txt',
    'Pytt/diaco.txt',
    'Pytt2/vallerga.txt',
    'Pytt3/vallerga.txt',
    'Pytt4/mangialavori.txt',
    'Pytt5/paolo.txt',
]

TEST_CFG = {
    "local_dir_state_path": LOCAL_DIR_STATE_FOR_TEST, 
    "sharing_path": TEST_SHARING_FOLDER, 
    "cmd_address": "localhost", 
    "cmd_port": 60001, 
    "api_suffix": "/API/V1/", 
    # no server_addre for sure
    "server_address": "", 
    "user": "user", 
    "pass": "pass", 
    "timeout_listener_sock": 0.5, 
    "backlog_listener_sock": 1
}

def timestamp_generator():
    timestamp_generator.__test__ = False
    return long(time.time()*10000)


def create_folder():
    os.makedirs(CONFIG_DIR)
    os.mkdir(TEST_SHARING_FOLDER)
    # os.makedirs(CONFIG_DIR)
    

    # with open(CONFIG_FILEPATH,'w') as f:
    #     json.dump(TEST_CFG, f, skipkeys=True, ensure_ascii=True, indent=4)


def destroy_folder():    
    shutil.rmtree(TEST_DIR)    

class TestClientDaemon(unittest.TestCase):
    def setUp(self):
        create_folder()
        

    def tearDown(self):
        pass

    def test_sync_process_new_on_server_new_on_client(self):
        """
        Test the case: (it must copy or move the file)
        Directory modified,
        timestamp client < timestamp server
        new file on server and new on client
        """

        print "sto testando...puppa!"

# import hashlib
# import unittest
# import os
# import shutil
# import json
# import time
# import random

# import httpretty
# import client_daemon


# start_dir = os.getcwd()

# TEST_DIR = os.path.join(os.environ['HOME'], 'daemon_test')
# CONFIG_DIR = os.path.join(TEST_DIR, '.PyBox')
# TEST_SHARING_FOLDER = os.path.join(TEST_DIR, 'test_sharing_folder')
# CONFIG_FILEPATH = os.path.join(CONFIG_DIR, 'daemon_config')

# LOCAL_DIR_STATE_FOR_TEST = os.path.join(TEST_DIR, 'test_local_dir_state')
# LAST_TIMESTAMP = 'last_timestamp'
# GLOBAL_MD5 = 'global_md5'
# SERVER_TIMESTAMP = 1

# def timestamp_generator():
#     return long(time.time()*10000)

# base_dir_tree = {
#     # <filepath>: (<timestamp>, <md5>)
   
# }

# LIST_OF_TEST_FILES = [
#     'ciao.txt',
#     'carlo.txt',
#     './Pytt/diaco.txt',
#     'pasquale.cat',
#     'carlo.buo',
#     'folder/carlo.buo'
# ]

# def folder_modified():
#     """
#     Return True to indicate that sharing folder is modified during daemon is down
#     """
#     return True

# def folder_not_modified():
#     """
#     Return True to indicate that sharing folder is modified during daemon is down
#     """
#     return False

# def create_test_sharing_folder():
#     if os.path.exists(TEST_SHARING_FOLDER):
#         shutil.rmtree(TEST_SHARING_FOLDER)
    
#     os.makedirs(TEST_SHARING_FOLDER)
#     base_dir_tree = {}
#     for path in LIST_OF_TEST_FILES:
#         abs_path = os.path.join(TEST_SHARING_FOLDER, path)
#         time_stamp = create_file(abs_path, 'a' * random.randint(1, 500000))
#         md5 = hashlib.md5().update(hashlib.md5(abs_path).hexdigest())
        
#         base_dir_tree[path] = [time_stamp, md5]
    

# def setup_test_dir():
#     """
#     Create (if needed) <TEST_DIR> directory starting from current directory and change current directory to the new one.
#     """
#     try:
#         os.mkdir(TEST_DIR)
#     except OSError:
#         pass

#     os.chdir(TEST_DIR)
#     create_test_sharing_folder()


# def tear_down_test_dir():
#     """
#     Return to initial directory and remove the <TEST_DIR> one.
#     """
#     os.chdir(start_dir)
#     shutil.rmtree(TEST_DIR)


# def create_file(file_path, content=''):
#     """
#     Write <content> (default: '') into <file_path> and return a long timestamp
#     of created file, also creating inner directories if needed.
#     :param file_path: str
#     :param content: str
#     :return: float
#     """
#     print 'Creating "{}"'.format(file_path)
#     dirname = os.path.dirname(file_path)
#     if not os.path.exists(dirname):
#         os.makedirs(dirname)

#     assert os.path.isdir(dirname), '{} must be a directory'.format(dirname)

#     with open(file_path, 'w') as fp:
#         fp.write(content)
#     return timestamp_generator()


# class FileFakeEvent(object):
#     """
#     Class that simulates a file related event sent from watchdog.
#     Actually create <src_path> and <dest_path> attributes and the file in disk.
#     """
#     def __init__(self, src_path, content='', dest_path=None):
#         self.src_path = src_path
#         create_file(self.src_path, content=content)
#         self.dest_path = dest_path


# class TestClientDaemon(unittest.TestCase):
#     def setUp(self):
#         setup_test_dir()
               
#         self.test_daemon = client_daemon.Daemon()
#         client_daemon.Daemon().F
#         self.test_daemon.create_observer()

#     def tearDown(self):
#         tear_down_test_dir()

#     def test_sync_process_new_on_server_new_on_client(self):
#         """
#         Test the case: (it must copy or move the file)
#         Directory modified,
#         timestamp client < timestamp server
#         new file on server and new on client
#         """
        
#         server_timestamp = timestamp_generator()
        
#         # server tree and client tree are the same
#         server_dir_tree = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()

#         old_global_md5_client = self.test_daemon.md5_of_client_snapshot()
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp - 1, 
#                                             GLOBAL_MD5: old_global_md5_client}
        
#         # changed client_snapshot and server_dir_tree        
#         self.test_daemon.client_snapshot.update({'new_file_on_client.txt': ('', '135687975431asdqweva')})        
#         server_dir_tree.update({'new_file_on_server.txt': (server_timestamp, '135617975431aytdxeva')})

#         new_global_md5_client = self.test_daemon.md5_of_client_snapshot()       

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, server_dir_tree),
#             [('download', 'new_file_on_server.txt'), ('upload', 'new_file_on_client.txt')]
#         )
#         self.assertNotEqual(new_global_md5_client, old_global_md5_client)

#     def test_sync_process_move(self):
#         """
#         Test the case: file moved on server
#         Client Directory NOT modified,
#         timestamp client < timestamp server        
#         """
#         same_md5 = '135617975431aytdxeva'

#         server_timestamp = timestamp_generator()
        
#         # created new file there will be moved
#         tmp_base_dir_tree = base_dir_tree.copy()        
#         tmp_base_dir_tree.update({'file_that_will_be_moved.txt': (server_timestamp, same_md5)})


#         # server tree and client tree are the same
#         server_dir_tree = tmp_base_dir_tree.copy()        
#         self.test_daemon.client_snapshot = tmp_base_dir_tree.copy()        

#         # the local_dir_state is updated to the last operation on server
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, 
#                                             GLOBAL_MD5: self.test_daemon.md5_of_client_snapshot()}

#         # moved/renamed file on server
#         moved_timestamp = timestamp_generator()
#         server_dir_tree.pop('file_that_will_be_moved.txt')
#         server_dir_tree.update({'file_moved.txt': (server_timestamp, same_md5)})
        
#         self.assertEqual(
#             self.test_daemon._sync_process(moved_timestamp, server_dir_tree),
#             []
#         )    

#     def test_sync_process_directory_not_modified1(self):
#         """
#         Test the case: (it must do nothing)
#         Directory not modified,
#         timestamp client == timestamp server
#         """
#         self.test_daemon._is_directory_modified = folder_not_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, GLOBAL_MD5: ''}
#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             []
#         )    

#     def test_sync_process_directory_not_modified2(self):
#         """
#         Test the case: (it must download the file)
#         Directory not modified,
#         timestamp client < timestamp server
#         new file on server and not in client
#         """
#         self.test_daemon._is_directory_modified = folder_not_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         files.update({'new': (18, 'md5md6jkshkfv')})
#         self.test_daemon.client_snapshot = base_dir_tree.copy()

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             [('download', 'new'), ]
#         )

#     def test_sync_process_directory_not_modified3(self):
#         """
#         Test the case: (it must copy or rename the file)
#         Directory not modified,
#         timestamp client < timestamp server
#         new file on server and in client but with different filepath
#         """
#         self.test_daemon._is_directory_modified = folder_not_modified
#         client_timestamp = 17
#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: client_timestamp, GLOBAL_MD5: ''}

#         # created file on base_dir_tree
#         md5_of_file = 'grergsfs78df78sf78'
#         base_dir_tree['new_file.txt'] = [client_timestamp, md5_of_file]

#         # server_dir_tree and client_snapshot starts equal
#         server_dir_tree = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()

#         # Created a copy of new_file.txt into the server
#         server_dir_tree['copy_new_file.txt'] = [server_timestamp, md5_of_file]

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, server_dir_tree),
#             []
#         )

#     def test_sync_process_directory_not_modified4(self):
#         """
#         Test the case: (it must download the file)
#         Directory not modified,
#         timestamp client < timestamp server
#         file modified on server
#         """
#         self.test_daemon._is_directory_modified = folder_not_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         files['carlo.txt'] = (server_timestamp, 'md5 diverso')

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             [('download', 'carlo.txt'), ]
#         )

#     def test_sync_process_directory_not_modified5(self):
#         """
#         Test the case: (it must delete the file on client)
#         Directory not modified,
#         timestamp client < timestamp server
#         file is missing on server
#         """
#         self.test_daemon._is_directory_modified = folder_not_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         self.test_daemon.client_snapshot.update({'carlito.txt': (1, 'jkdhlghkg')})

#         self.assertEqual(self.test_daemon._sync_process(server_timestamp, files), [])

#     def test_sync_process_directory_modified1(self):
#         """
#         Test the case: (it must do nothing)
#         Directory modified,
#         timestamp client == timestamp server
#         client is already synchronized with server
#         """
#         self.test_daemon._is_directory_modified = folder_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             []
#         )

#     def test_sync_process_directory_modified2(self):
#         """
#         Test the case: (it must delete the file on server)
#         Directory modified,
#         timestamp client == timestamp server
#         new file on server and not on client
#         """
#         self.test_daemon._is_directory_modified = folder_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         files.update({'new': (18, 'md5md6jkshkfv')})

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             [('delete', 'new')]
#         )

#     def test_sync_process_directory_modified3(self):
#         """
#         Test the case: (it must modify the file on server)
#         Directory modified,
#         timestamp client == timestamp server
#         file modified
#         """
#         self.test_daemon._is_directory_modified = folder_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         files['carlo.txt'] = (server_timestamp, 'md5 diverso')

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             [('modified', 'carlo.txt')]
#         )

#     def test_sync_process_directory_modified4(self):
#         """
#         Test the case: (it must upload the file on server)
#         Directory modified,
#         timestamp client == timestamp server
#         new file in client and not on server
#         """
#         self.test_daemon._is_directory_modified = folder_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         files.pop('carlo.txt')

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             [('upload', 'carlo.txt')]
#         )

#     def test_sync_process_directory_modified5(self):
#         """
#         Test the case: (it must download the file)
#         Directory modified,
#         timestamp client < timestamp server
#         new file on server and not in client
#         file timestamp > client timestamp
#         """
#         self.test_daemon._is_directory_modified = folder_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         files.update({'new': (18, 'md5md6jkshkfv')})

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             [('download', 'new')]
#         )

#     def test_sync_process_directory_modified6(self):
#         """
#         Test the case: (it must delete the file)
#         Directory modified,
#         timestamp client < timestamp server
#         new file on server and not in client
#         file timestamp < client timestamp
#         """
#         self.test_daemon._is_directory_modified = folder_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         files.update({'new': (16, 'md5md6jkshkfv')})

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             [('delete', 'new')]
#         )   
    

#     def test_sync_process_directory_modified8(self):
#         """
#         Test the case: (it must modify the file on server)
#         Directory modified,
#         timestamp client < timestamp server
#         file modified
#         file timestamp < client timestamp
#         """
#         self.test_daemon._is_directory_modified = folder_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         files['carlo.txt'] = (16, 'md5md6jkshkfv')

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             [('modify', 'carlo.txt')]
#         )

#     def test_sync_process_directory_modified9(self):
#         """
#         Test the case: (there is a conflict, so it upload the file on server with ".conflicted" extension)
#         Directory modified,
#         timestamp client < timestamp server
#         file modified
#         file timestamp > client timestamp
#         """
#         self.test_daemon._is_directory_modified = folder_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         files['carlo.txt'] = (18, 'md5md6jkshkfv')

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             [('upload', ''.join(['carlo.txt', '.conflicted']))]
#         )

#     def test_sync_process_directory_modified10(self):
#         """
#         Test the case: (it upload the file on server)
#         Directory modified,
#         timestamp client < timestamp server
#         new file in client and not on server
#         """
#         self.test_daemon._is_directory_modified = folder_modified

#         server_timestamp = 18
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

#         files = base_dir_tree.copy()
#         self.test_daemon.client_snapshot = base_dir_tree.copy()
#         files.pop('carlo.txt')

#         self.assertEqual(
#             self.test_daemon._sync_process(server_timestamp, files),
#             [('upload', 'carlo.txt')]
#         )

# class TestClientDaemonOnEvents(unittest.TestCase):
#     """
#     Test the "on_<something>" client daemon, triggered by watchdog.
#     """


#     def setUp(self):
#         # Create and go into the test directory
#         create_test_sharing_folder()
#         setup_test_dir()
#         httpretty.enable()

#         #self.cm = ConnectionManager()
#         with open(CONFIG_FILEPATH) as fo:
#             self.cfg = json.load(fo)

#         self.auth = self.cfg['user'], self.cfg['pass']
#         self.cfg['server_address'] = "http://localhost:5000"

#         # load local_dir_state file for testing
#         self.cfg['local_dir_state_path'] = LOCAL_DIR_STATE_FOR_TEST

#         # create this auth testing
#         self.authServerAddress = "http://" + self.cfg['user'] + ":" + self.cfg['pass']
#         self.base_url = self.cfg['server_address'] + self.cfg['api_suffix']
#         self.files_url = self.base_url + 'files/'
#         self.actions_url = self.base_url + 'actions/'

#         # Instantiate the daemon
#         self.test_daemon = client_daemon.Daemon()
#         self.test_daemon.create_observer()

#         # Injecting a fake client snapshot
#         path = 'dir/file.txt'
#         md5 = '50abe822532a06fb733ea3bc089527af'
#         ts = timestamp_generator()
#         self.test_daemon.client_snapshot = {path: [ts, md5]}
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: ts, GLOBAL_MD5: md5}

#     def tearDown(self):
#         if os.path.exists(LOCAL_DIR_STATE_FOR_TEST):
#             os.remove(LOCAL_DIR_STATE_FOR_TEST)
#         httpretty.disable()
#         httpretty.reset()
#         # Remove the test directory.
#         tear_down_test_dir()

#     def test_md5_of_client_snapshot(self, verbose = 1):
#         """
#         Test the Daemons function
#         """
#         md5Hash = hashlib.md5()

#         for path, time_md5 in self.test_daemon.client_snapshot.items():
#             # extract md5 from tuple. we don't need hexdigest it's already md5
#             md5Hash.update(time_md5[1])
#             md5Hash.update(hashlib.md5(path).hexdigest())

#         response_of_function = self.test_daemon.md5_of_client_snapshot()
#         self.assertNotEqual(response_of_function,'50abe822532a06fb733ea3bc089527af')
#         self.assertEqual(response_of_function,md5Hash.hexdigest())

#     @httpretty.activate
#     def test_on_created(self):
#         """
#         Test on_created method of daemon when a new file is created.
#         """
#         before_local_dir_state = self.test_daemon.local_dir_state.copy()
#         ts1 = before_local_dir_state[LAST_TIMESTAMP]
#         ts2 = ts1 + 60  # arbitrary value

#         # new file I'm going to create in client sharing folder
#         new_path = 'created_file.txt'

#         url = self.files_url + new_path
#         httpretty.register_uri(httpretty.POST, url, status=201,
#                                body='{"server_timestamp":%d}' % ts2,
#                                content_type="application/json")

#         abs_path = os.path.join(self.test_daemon.cfg['sharing_path'], new_path)
#         event = FileFakeEvent(abs_path)

#         self.test_daemon.on_created(event)
#         # test that the new path is in the client_snapshot
#         self.assertIn(new_path, self.test_daemon.client_snapshot)
#         # simply check that local_dir_state is changed
#         self.assertNotEqual(before_local_dir_state, self.test_daemon.local_dir_state)

#         # # daemon.local_dir_state should be a dict
#         self.assertIsInstance(self.test_daemon.local_dir_state, dict)
#         # last_timestamp should be an long
#         self.assertIsInstance(self.test_daemon.local_dir_state[LAST_TIMESTAMP], long)
#         # test exact value of timestamp
#         self.assertEqual(self.test_daemon.local_dir_state[LAST_TIMESTAMP], ts2)

#     @httpretty.activate
#     def test_on_moved(self):
#         """
#         Test that daemon on_moved method cause the user path being correctly moved inside client_snapshot attribute,
#         global md5 changed, last timestamp correctly updated and local dir state saved.
#         """
#         # Create arbitrary initial values.
#         timestamp_start = timestamp_generator()
#         timestamp_end = timestamp_start + 1
#         global_md5_start = 'fake global md5'  # the real value doesn't really matter in this test.

#         src_path = 'dir1/tomove.txt'
#         dest_path = 'dir2/tomove.txt'
#         content = 'arbitrary content'
#         md5 = hashlib.md5(content).hexdigest()

#         # Create daemon initial state.
#         self.test_daemon.client_snapshot = {src_path: [timestamp_start, md5]}  # the path that will be moved.
#         self.test_daemon.local_dir_state = {LAST_TIMESTAMP: timestamp_start, GLOBAL_MD5: global_md5_start}

#         # Create fake event and file.
#         src_abs_path = os.path.join(self.cfg['sharing_path'], src_path)
#         dest_abs_path = os.path.join(self.cfg['sharing_path'], dest_path)
#         event = FileFakeEvent(src_abs_path, content, dest_abs_path)

#         # Create server response.
#         url = self.actions_url + 'move'  # NB: no final '/'!!!
#         httpretty.register_uri(httpretty.POST, url,
#                                status=200,
#                                body='{"server_timestamp":%d}' % timestamp_end,
#                                content_type="application/json")

#         # Store some initial values.
#         self.test_daemon.update_local_dir_state(timestamp_generator())
#         local_dir_state_start = self.test_daemon.local_dir_state

#         # Call method to test.
#         self.test_daemon.on_moved(event)

#         # Store some final values to be compared.
#         global_md5_received = self.test_daemon.local_dir_state[GLOBAL_MD5]
#         timestamp_received = self.test_daemon.local_dir_state[LAST_TIMESTAMP]

#         # Test assertions.
#         self.assertIn(dest_path, self.test_daemon.client_snapshot)
#         self.assertNotIn(src_path, self.test_daemon.client_snapshot)

#         # md5 must be changed.
#         self.assertNotEqual(local_dir_state_start[GLOBAL_MD5], global_md5_start)

#         # Last timestamp must be correctly updated with which one received from server.
#         self.assertEqual(timestamp_received, timestamp_end)

#         # Check that state is saved on disk by checking if current file timestamp
#         # is greater than the starting one.
#         with open (self.cfg['local_dir_state_path'],'r') as ldr:
#             local_dir_state_loaded = json.load(ldr)
#         self.assertEqual(local_dir_state_loaded['global_md5'], global_md5_received)
#         self.assertEqual(local_dir_state_loaded['server_timestamp'], timestamp_received)


# if __name__ == '__main__':
#     unittest.main()