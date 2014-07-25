import hashlib
import unittest
import os
import sys
import shutil
import json
import time
import random
# import httpretty
import client_daemon
import test_utils

TEST_DIR = os.path.join(os.environ['HOME'], 'daemon_test')
CONFIG_DIR = os.path.join(TEST_DIR, '.PyBox')
CONFIG_FILEPATH = os.path.join(CONFIG_DIR, 'daemon_config')
LOCAL_DIR_STATE_FOR_TEST = os.path.join(CONFIG_DIR, 'local_dir_state')

TEST_SHARING_FOLDER = os.path.join(TEST_DIR, 'test_sharing_folder')

LIST_OF_TEST_FILES = [
    'file1.txt',
    'file2.txt',
    'documents/diaco.txt',
    'images/image.txt',
    'videos/video.txt',
    'folder/pysqualo.txt',
    'folder2/paolo.txt',
    'folder3/luca.txt',
    'folder4/roxana.txt',
    'folder5/fabrizio.txt',
    'folder6/iacopy.txt',
]

base_dir_tree = {}

TEST_CFG = {
    "local_dir_state_path": LOCAL_DIR_STATE_FOR_TEST,
    "sharing_path": TEST_SHARING_FOLDER,
    "cmd_address": "localhost",
    "cmd_port": 60001,
    "api_suffix": "/API/V1/",
    # no server_address to be sure
    "server_address": "",
    "user": "user",
    "pass": "pass",
    "activate": True,
}

def timestamp_generator():
    timestamp_generator.__test__ = False
    return long(time.time()*10000)

def create_base_dir_tree(list_of_files = LIST_OF_TEST_FILES):
    global base_dir_tree
    base_dir_tree = {}
    for path in list_of_files:
        time_stamp = timestamp_generator()
        md5 = hashlib.md5(path).hexdigest()
        base_dir_tree[path] = [time_stamp, md5]

def create_environment():
    if not os.path.exists(TEST_DIR):
        os.makedirs(CONFIG_DIR)
        os.mkdir(TEST_SHARING_FOLDER)

    with open(CONFIG_FILEPATH,'w') as f:
            json.dump(TEST_CFG, f, skipkeys=True, ensure_ascii=True, indent=4)

def create_files(dir_tree):

    for path in dir_tree:
        file_path = os.path.join(TEST_SHARING_FOLDER, path)
        dirname = os.path.dirname(file_path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        with open(file_path, 'w') as f:
            f.write(file_path)

def destroy_folder():
    shutil.rmtree(TEST_DIR)

def fake_make_move(self, src, dst, timestamp):

    self.operation_happened = "move: src "+src+" dst: "+dst
    return True

def fake_make_copy(self, src, dst, timestamp):

    self.operation_happened = "copy: src "+src+" dst: "+dst
    return True

class TestClientDaemon(unittest.TestCase):

    def setUp(self):
        create_environment()
        create_base_dir_tree()
        self.daemon = client_daemon.Daemon(CONFIG_FILEPATH, TEST_SHARING_FOLDER)
        self.daemon.operation_happened = 'initial'
        self.daemon.create_observer()

    def tearDown(self):
        global base_dir_tree
        base_dir_tree = {}
        destroy_folder()

    def test__build_directory(self):
        """
        Create directory
        :return: boolean value, True is created or already existent
        """
        self.assertTrue(self.daemon._build_directory('cartella_di_prova'))
        self.assertTrue(self.daemon._build_directory('cartella_di_prova'))

    def test__build_directory_in_forbidend_path(self):
        """
        Create directory in forbiden path
        :return:boolean value, False if the path is not allowed
        """
        self.assertFalse(self.daemon._build_directory('/cartella_di_prova'))
    def test_md5_of_client_snapshot(self):
        """
        Test MD5_OF_CLIENT_SNAPSHOT: Check the global_md5_method
        :return:
        """

        time_stamp = timestamp_generator()
        self.daemon.client_snapshot = base_dir_tree.copy()

        md5Hash = hashlib.md5()

        for path, time_md5 in sorted(self.daemon.client_snapshot.items()):
            # extract md5 from tuple. we don't need hexdigest it's already md5

            md5Hash.update(time_md5[1])
            md5Hash.update(path)

        self.daemon.md5_of_client_snapshot()
        self.assertEqual(md5Hash.hexdigest(),self.daemon.md5_of_client_snapshot())

    def test_is_directory_not_modified(self):

        self.daemon.client_snapshot = base_dir_tree.copy()

        self.daemon.update_local_dir_state(timestamp_generator())

        old_global_md5 = self.daemon.local_dir_state['global_md5']

        is_dir_modified_result = self.daemon._is_directory_modified()

        test_md5 = self.daemon.local_dir_state['global_md5']

        print self.daemon.local_dir_state

        self.assertFalse(is_dir_modified_result)
        self.assertEqual(old_global_md5, test_md5)


    def test_md5_of_client_snapshot_added_file(self):
        """
        Test MD5_OF_CLIENT_SNAPSHOT: Check the global_md5_method when i have update the client_snapshot
        :return:
        """

        time_stamp = timestamp_generator()
        self.daemon.client_snapshot = base_dir_tree.copy()
        old_global_md5 = self.daemon.md5_of_client_snapshot()
        self.daemon.client_snapshot['filepath'] = [time_stamp, '10924784659832']

        self.assertNotEqual(old_global_md5, self.daemon.md5_of_client_snapshot())
        self.assertEqual(self.daemon.md5_of_client_snapshot(), self.daemon.md5_of_client_snapshot())

    def test_save_local_dir_state(self):
        """
        Test LOCAL_DIR_STATE:  Test that the local_dir_state saved is equal to the loaded
        :return:
        """
        time_stamp = timestamp_generator()
        self.daemon.client_snapshot = base_dir_tree.copy()
        self.daemon.update_local_dir_state(time_stamp)
        self.daemon.load_local_dir_state()

        self.assertEqual(self.daemon.local_dir_state['global_md5'], self.daemon.md5_of_client_snapshot(), msg="The global_md5 i save is the save i load")
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'], time_stamp, msg="The timestamp i save is the save i load")

    ####################### DIRECTORY NOT MODIFIED #####################################
    def test_sync_process_move_on_server(self):

        """
        Test SYNC: Test only the calling of _make_move by _sync_process, server_timestamp > client_timestamp
        Directory NOT modified
        """

        # Overriding sync methods of Class Daemon
        client_daemon.Daemon._make_move_on_client = fake_make_move

        server_timestamp = timestamp_generator()

        # server tree and client tree starting with the same situation
        server_dir_tree = base_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()

        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # client timestamp < server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp - 4, 'global_md5': old_global_md5_client}

        # Added to copy of file1.txt
        timestamp_and_md5_of_copied_file = server_dir_tree.pop('file1.txt')
        server_dir_tree['move_folder/file1.txt'] = timestamp_and_md5_of_copied_file

        # the src and destination of the file moved
        src = 'file1.txt'
        dst = 'move_folder/file1.txt'

        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
                        [])
        self.assertEqual(self.daemon.operation_happened,
                        "move: src "+src+" dst: "+dst)

    def test_sync_process_copy_on_server(self):
        """
        Test SYNC: Test only calling of _make_copy by sync, server_timestamp > client_timestamp
        Directory NOT modified
        """

        # Overriding sync methods
        client_daemon.Daemon._make_copy_on_client = fake_make_copy

        server_timestamp = timestamp_generator()

        # server tree and client tree starting with the same situation
        server_dir_tree = base_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()

        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # client timestamp < server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp - 4, 'global_md5': old_global_md5_client}

        # Added to copy of file1.txt
        timestamp_and_md5_of_copied_file = server_dir_tree['file1.txt']
        server_dir_tree['copy_folder/file1.txt'] = timestamp_and_md5_of_copied_file

        # the src and destination of the file copied
        src = 'file1.txt'
        dst = 'copy_folder/file1.txt'

        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
                        [])
        self.assertEqual(self.daemon.operation_happened,
                        "copy: src "+src+" dst: "+dst)

    def test_sync_process_new_on_server(self):
        """
        Test SYNC: New file on server, server_timestamp > client_timestamp
        Directory NOT MODIFIED
        """

        server_timestamp = timestamp_generator()

        # server tree and client tree are the same here
        server_dir_tree = base_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()

        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # client_timestamp < server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp - 1, 'global_md5': old_global_md5_client}

        # After that new file on server
        server_dir_tree.update({'new_file_on_server.txt': (server_timestamp, '98746548972341')})

        new_global_md5_client = self.daemon.md5_of_client_snapshot()

        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
                         [('download', 'new_file_on_server.txt')]
        )
        # Local Directory is NOT MODIFIED
        self.assertEqual(new_global_md5_client, old_global_md5_client)

    ####################### TEST MOVE and COPY ON CLIENT ##############################

    def test_make_copy_function(self):
        """
        Test _MAKE_COPY: test the COPY function when the DST NOT EXISTS
        :return:
        """

        create_base_dir_tree(['file1.txt'])
        self.daemon.client_snapshot = base_dir_tree.copy()
        server_timestamp = timestamp_generator()
        # Create the files in client_snapshot / base_dir_tree
        create_files(self.daemon.client_snapshot)

        file_to_copy = 'file1.txt'
        dst_file_of_copy = 'fake2/copy_file1.txt'

        md5_before_copy = self.daemon.md5_of_client_snapshot()
        self.assertEqual(self.daemon._make_copy_on_client(file_to_copy, dst_file_of_copy, server_timestamp), True)


        self.assertIn('fake2/copy_file1.txt', self.daemon.client_snapshot)
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'], server_timestamp)
        self.assertNotEqual(self.daemon.local_dir_state['global_md5'], md5_before_copy)

    def test_make_copy_function_src_file_not_exists(self):
        """
        Test _MAKE_COPY: test the COPY function when the SRC NOT EXISTS
        :return:
        """

        create_base_dir_tree([])
        self.daemon.client_snapshot = base_dir_tree.copy()

        # Create the files in client_snapshot / base_dir_tree

        create_files(self.daemon.client_snapshot)
        server_timestamp = timestamp_generator()
        md5_before_copy = self.daemon.md5_of_client_snapshot()

        # Initialize local_dir_state
        self.daemon.local_dir_state['last_timestamp'] = server_timestamp - 5
        self.daemon.local_dir_state['global_md5'] = md5_before_copy

        file_to_be_move_not_exists = 'i_do_not_exist.txt'
        dst_file_that_not_exists = 'fake2/move_file1.txt'

        self.assertEqual(self.daemon._make_copy_on_client(file_to_be_move_not_exists, dst_file_that_not_exists, server_timestamp), False)
        self.assertNotIn('fake2/move_file1.txt', self.daemon.client_snapshot)

        # if copy fail local dir state must be unchanged
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'], server_timestamp - 5)
        self.assertEqual(self.daemon.local_dir_state['global_md5'], md5_before_copy)

    def test_make_move_function(self):
        """
        Test _MAKE_MOVE: test if a destination path doesn't exists when the function is making a MOVE
        :expect value: True
        """
        create_base_dir_tree(['file1.txt'])
        self.daemon.client_snapshot = base_dir_tree.copy()
        server_timestamp = timestamp_generator()
        # Create the files in client_snapshot / base_dir_tree

        create_files(self.daemon.client_snapshot)
        md5_before_move = self.daemon.md5_of_client_snapshot()

        file_to_move_exists = 'file1.txt'
        dst_file_that_not_exists = 'fake2/move_file1.txt'

        self.assertEqual(self.daemon._make_move_on_client(file_to_move_exists, dst_file_that_not_exists, server_timestamp), True)
        self.assertNotIn(file_to_move_exists, self.daemon.client_snapshot)
        self.assertIn(dst_file_that_not_exists, self.daemon.client_snapshot)

        # test local dir state after movement
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'], server_timestamp)
        self.assertNotEqual(self.daemon.local_dir_state['global_md5'], md5_before_move)

    def test_make_move_function_src_file_not_exists(self):
        """
        Test _MAKE_MOVE: test the MOVE function when the SRC NOT EXISTS
        :expect value: False
        """
        self.daemon.client_snapshot = base_dir_tree.copy()

        # Create the files in client_snapshot / base_dir_tree

        create_files(self.daemon.client_snapshot)
        server_timestamp = timestamp_generator()

        # Initialize local_dir_state
        self.daemon.local_dir_state['last_timestamp'] = server_timestamp - 5
        self.daemon.local_dir_state['global_md5'] = self.daemon.md5_of_client_snapshot()

        file_to_be_move_not_exists = 'i_do_not_exist.txt'
        dst_file_that_not_exists = 'fake2/move_file1.txt'

        self.assertEqual(self.daemon._make_move_on_client(file_to_be_move_not_exists, dst_file_that_not_exists, server_timestamp), False)

        # test local dir state after movement
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'], server_timestamp - 5)
        self.assertEqual(self.daemon.local_dir_state['global_md5'], self.daemon.md5_of_client_snapshot())

    def test_make_move_function_dst_file_exists(self):
        """
        Test _MAKE_MOVE: test the MOVE function when the DST EXISTS
        :return:
        """

        create_base_dir_tree(['file1.txt','move_folder/file1.txt'])
        self.daemon.client_snapshot = base_dir_tree.copy()

        # Create the files in client_snapshot / base_dir_tree
        create_files(self.daemon.client_snapshot)
        server_timestamp = timestamp_generator()
        file_to_move = 'file1.txt'
        dst_file_exists = 'move_folder/file1.txt'

        self.assertEqual(self.daemon._make_move_on_client(file_to_move, dst_file_exists, server_timestamp), True)


    ####################### DIRECTORY MODIFIED #####################################
    def test_sync_process_new_on_server_new_on_client(self):
        """
        Test SYNC: new file on server, new on client, server_timestamp > client_timestamp
        Directory modified
        """

        server_timestamp = timestamp_generator()

        # server tree and client tree are the same
        server_dir_tree = base_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()

        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # Daemon timestamp < server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp - 1,'global_md5': old_global_md5_client}

        # After that new file on server and new on client
        self.daemon.client_snapshot.update({'new_file_on_client.txt': (server_timestamp, '321456879')})
        server_dir_tree.update({'new_file_on_server.txt': (server_timestamp, '98746548972341')})

        new_global_md5_client = self.daemon.md5_of_client_snapshot()

        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
                         [('download', 'new_file_on_server.txt'), ('upload', 'new_file_on_client.txt')]
                        )

        # Local Directory is MODIFIED
        self.assertNotEqual(new_global_md5_client, old_global_md5_client)

    def test_sync_process_modified_on_server_modified_on_client(self):

        """
        Test SYNC: modified file on server, modified same file on client, server_timestamp > client_timestamp
        Directory modified
        """

        server_timestamp = timestamp_generator()

        # server tree and client tree starting with the same situation
        server_dir_tree = base_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()

        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # Daemon timestamp < server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp - 1, 'global_md5': old_global_md5_client}

        # After that there will be modified file on server and modified same file on client.
        # Client file have to win for time_stamp
        self.daemon.client_snapshot['file.txt'] = (server_timestamp, '321456879')
        server_dir_tree['file.txt'] = (server_timestamp - 4, '987456321')

        new_global_md5_client = self.daemon.md5_of_client_snapshot()

        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
                         [('modify', 'file.txt')]
                        )

        # Local Directory is MODIFIED
        self.assertNotEqual(new_global_md5_client, old_global_md5_client)

class TestDaemonCmdManagerConnection(unittest.TestCase):
    def setUp(self):
        self.client_daemon = client_daemon.Daemon()
        self.client_daemon.create_observer()
        self.socket = test_utils.FakeSocket()

    def test_get_cmdmanager_request(self):
        command = {'shutdown': ()}
        json_data = json.dumps(command)
        self.socket.set_response(json_data)

        self.assertEquals(self.client_daemon._get_cmdmanager_request(self.socket), json.loads(json_data))

    def test_set_cmdmanager_response(self):
        response = 'testtestetst'
        self.assertEqual(self.client_daemon._set_cmdmanager_response(self.socket, response),
                         json.dumps({'message': response}))
