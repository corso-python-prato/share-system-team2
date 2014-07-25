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
    "timeout_listener_sock": 0.5, 
    "backlog_listener_sock": 1
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
        self.daemon = client_daemon.Daemon(CONFIG_FILEPATH)
        self.daemon.operation_happened = 'initial'
        self.daemon.create_observer()

    def tearDown(self):
        global base_dir_tree
        base_dir_tree = {}
        destroy_folder()

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

    def test_sync_process_delete(self):
        """
        Test SYNC: New file on server, server_timestamp > client_timestamp
        but file_timestamp < client_timestamp
        Directory MODIFIED
        """

        # only file that i really need
        create_base_dir_tree(['file_test_delete.txt', 'file_mp3_test_delete.mp3'])
        server_timestamp = timestamp_generator()

        # Server and client are the same
        self.daemon.client_snapshot = base_dir_tree.copy()
        server_dir_tree = base_dir_tree.copy()

        # client timestamp < server timestamp
        self.daemon.local_dir_state['last_timestamp'] = server_timestamp - 1
        # directory modified
        self.daemon.local_dir_state['global_md5'] = 'md5diversodaquelloeffettivo'

        # file_timestamp < client_timestamp
        server_dir_tree.update({'new_file': (server_timestamp - 2, 'md5md6jkshkfv')})
        self.assertEqual(
            self.daemon._sync_process(server_timestamp, server_dir_tree),
            [('delete', 'new_file')])

    def test_sync_process_local_dir_modified_client_ts_equal_server_ts(self):
        """
        Test SYNC: server_timestamp == client_timestamp
        Directory MODIFIED
        the client rules because dir is modified
        """

        create_base_dir_tree(['file_test.txt', 'file_mp3_test.mp3'])
        server_timestamp = timestamp_generator()

        # Server and client are the same
        self.daemon.client_snapshot = base_dir_tree.copy()
        server_dir_tree = base_dir_tree.copy()

        # server ts and client ts are the same
        self.daemon.local_dir_state['last_timestamp'] = server_timestamp
        # directory not modified
        self.daemon.local_dir_state['global_md5'] = self.daemon.md5_of_client_snapshot()

        self.daemon.client_snapshot['file.txt'] = (server_timestamp -1, '321456879')
        self.daemon.client_snapshot['file_test.txt'] = (server_timestamp -1, '123654789')
        server_dir_tree.update({'new_file_on_server': (server_timestamp - 2, 'md5md6jkshkfv')})

        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
            [('delete', 'new_file_on_server'),
            ('modify', 'file_test.txt'),
            ('upload', 'file.txt')])

    def test_sync_move_on_server(self):
        """
        Test SYNC: server_timestamp > client_timestamp test MOVE on server
        Directory MODIFIED
        copy or move? move on server
        """

        create_base_dir_tree(['file_test_move.txt', 'file_mp3_test_move.mp3'])
        server_timestamp = timestamp_generator()

        # Server and client starts the same
        self.daemon.client_snapshot = base_dir_tree.copy()
        server_dir_tree = base_dir_tree.copy()

        # server_ts > client_ts
        self.daemon.local_dir_state['last_timestamp'] = server_timestamp - 5
        self.daemon.local_dir_state['global_md5'] = self.daemon.md5_of_client_snapshot()

        # function _make_move_on_client
        self.daemon._make_move_on_client = self.mock_move_on_client

        # move the file on SERVER
        server_dir_tree['folder/file_test_moved.txt'] = server_dir_tree.pop('file_test_move.txt')

        # add a file to the client to modify the local_dir
        self.daemon.client_snapshot.update({'new_file_': (server_timestamp - 2, 'md5md6jkshkfv')})

        # the new file have to be uploaded
        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
             [('upload', 'new_file_')])

        # assure the move
        self.assertIn('folder/file_test_moved.txt',self.daemon.client_snapshot)
        self.assertNotIn('file_test_move.txt',self.daemon.client_snapshot)
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'], server_timestamp)

    def mock_move_on_client(self, src, dst, server_timestamp):

        self.daemon.client_snapshot[dst] = self.daemon.client_snapshot[src]
        self.daemon.client_snapshot.pop(src)
        self.daemon.update_local_dir_state(server_timestamp)
        return True

    def test_sync_process_copy_on_client(self):
        """
        Test SYNC: server_timestamp > client_timestamp test COPY on server
        Directory MODIFIED
        copy or move? copy
        """
        create_base_dir_tree(['file_test_copy_or_move.txt', 'file_mp3_test_copy_or_move.mp3'])
        server_timestamp = timestamp_generator()

        # Server and client starts the same
        self.daemon.client_snapshot = base_dir_tree.copy()
        server_dir_tree = base_dir_tree.copy()

        # add a the same file in server and client and then move it on SERVER
        self.daemon.client_snapshot['file_test_copy.txt'] = (server_timestamp -1, '987654321')
        server_dir_tree['file_test_copy.txt'] = (server_timestamp -1, '987654321')

        # copied file on server must be copied on client now
        server_dir_tree['file_test_copied.txt'] = (server_timestamp, '987654321')

        # server_ts > client_ts
        self.daemon.local_dir_state['last_timestamp'] = server_timestamp - 5
        self.daemon.local_dir_state['global_md5'] = self.daemon.md5_of_client_snapshot()

        # adding file to client_snapshot so dir will be  modified
        self.daemon.client_snapshot['another_file_modified.txt'] = (server_timestamp -1, '645987123')

        # mock the function. if not it will try to really move the file on disk
        self.daemon._make_copy_on_client = self.mock_copy_on_client

        # dir is modified so i've to find an upload
        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
            [('upload', 'another_file_modified.txt')])

        # check local dir state for the timestamp
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'],
                         server_timestamp)

        # the file copied must be in the client snapshot after the copy
        self.assertIn('file_test_copied.txt', self.daemon.client_snapshot)
        self.assertIn('file_test_copy.txt', self.daemon.client_snapshot)

    def mock_copy_on_client(self, src, dst, server_timestamp):

        self.daemon.client_snapshot[dst] = self.daemon.client_snapshot[src]
        self.daemon.update_local_dir_state(server_timestamp)
        return True

    def test_sync_process_conflicted_path(self):
        """
        Test SYNC: server_timestamp > client_timestamp
        Directory MODIFIED
        test same file MODIFIED in server and client, worst case
        """

        create_base_dir_tree(['file_test_conflicted.txt'])
        server_timestamp = timestamp_generator()

        # Server and client starts the same
        self.daemon.client_snapshot = base_dir_tree.copy()
        server_dir_tree = base_dir_tree.copy()

        # server_ts > client_ts
        self.daemon.local_dir_state['last_timestamp'] = server_timestamp - 5
        self.daemon.local_dir_state['global_md5'] = self.daemon.md5_of_client_snapshot()

        # mod same file (server has the most recent file)
        self.daemon.client_snapshot['file_test_conflicted.txt'] = (server_timestamp - 5, '321456879')
        server_dir_tree['file_test_conflicted.txt'] = (server_timestamp - 4, '987456321')

        expected_value = ''.join(['file_test_conflicted.txt', '.conflicted'])
        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
                        [('upload', expected_value)])

    def test_sync_process_stupid_case(self):
        """
        Test SYNC: server_timestamp == local_timestamp
        local directory NOT modified
        expected value []
        :return:
        """

        create_base_dir_tree(['just_a_file.txt'])
        server_timestamp = timestamp_generator()

        # Server and client starts the same
        self.daemon.client_snapshot = base_dir_tree.copy()
        server_dir_tree = base_dir_tree.copy()

        # server_ts == client_ts
        self.daemon.local_dir_state['last_timestamp'] = server_timestamp
        self.daemon.local_dir_state['global_md5'] = self.daemon.md5_of_client_snapshot()

        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
                         [])

    def test_build_client_snap_regex(self):
        """
        Test IGNORED REGEX: test build_client_snapshot
        """
        # create a base_dir_tree
        create_base_dir_tree(['just_a_file.txt', 'a_tmp_file.txt#', 'another_tmp_file.txt~'])

        # create the files for real
        create_files(base_dir_tree)

        # create the snapshot of real files
        self.daemon.build_client_snapshot()

        self.assertIn('just_a_file.txt', self.daemon.client_snapshot
                        )
        self.assertNotIn('a_tmp_file.txt#', self.daemon.client_snapshot
                        )
        self.assertNotIn('another_tmp_file.txt~', self.daemon.client_snapshot
                        )

    ################ TEST EVENTS ####################

    def test_on_created(self):
        """"
        Test EVENTS: test on created expect an UPLOAD
        """
        some_file = os.path.join(TEST_SHARING_FOLDER, 'file.txt')

        # replace connection manager in the client instance
        self.daemon.conn_mng = FakeConnMng()

        self.daemon.on_created(FileFakeEvent(src_path=some_file, content='Un po di testo'))
        self.assertIn('file.txt', self.daemon.client_snapshot)
        self.assertEqual(self.daemon.conn_mng.data_cmd, 'upload')

    def test_on_created_modify(self):
        """"
        Test EVENTS: test on created expect a MODIFY
        """

        some_file = os.path.join(TEST_SHARING_FOLDER, 'file.txt')

        # replace connection manager in the client instance
        self.daemon.conn_mng = FakeConnMng()

        create_base_dir_tree(['file.txt'])
        self.daemon.client_snapshot = base_dir_tree.copy()

        # the file it's in client_snapshot so when i create it the event it's detected as modify
        self.daemon.on_created(FileFakeEvent(src_path=some_file, content='Un po di testo'))
        self.assertIn('file.txt', self.daemon.client_snapshot)

        # check md5. must be the same
        self.assertEqual(self.daemon.client_snapshot['file.txt'][1], hashlib.md5('Un po di testo').hexdigest())
        self.assertEqual(self.daemon.conn_mng.data_cmd, 'modify')

    def test_on_created_copy(self):
        """"
        Test EVENTS: test on created expect a COPY
        """

        some_file = os.path.join(TEST_SHARING_FOLDER, 'another_file.txt')

        # replace connection manager in the client instance
        self.daemon.conn_mng = FakeConnMng()

        # creating client_snapshot {filepath:(timestamp, md5)}
        create_base_dir_tree(['file.txt'])
        self.daemon.client_snapshot = base_dir_tree.copy()

        # putting the filepath in the content generate the same md5 so must be a copy event
        self.daemon.on_created(FileFakeEvent(src_path=some_file, content='file.txt'))
        self.assertEqual(self.daemon.conn_mng.data_cmd, 'copy')
        self.assertEqual(self.daemon.conn_mng.data_file['dst'], 'another_file.txt')

        # the copy must be in the snapshot
        self.assertIn('another_file.txt', self.daemon.client_snapshot)



class FakeConnMng(object):

    def __init__(self):
        print "FakeConnMng created"
        self.data_cmd = ''
        self.data_file = ''

    def dispatch_request(self, data_cmd, data_file):
        self.data_cmd = data_cmd
        self.data_file = data_file
        return {'server_timestamp': time.time()*10000}


class FileFakeEvent(object):
    """
    Class that simulates a file related event sent from watchdog.
    Actually create <src_path> and <dest_path> attributes and the file in disk.
    """

    def __init__(self, src_path, content='', dest_path=None):
        self.src_path = src_path
        self.create_file(self.src_path, content=content)
        self.dest_path = dest_path

    def create_file(self, path, content=''):
        with open(path, 'w') as f:
            f.write(content)

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