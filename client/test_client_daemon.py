#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hashlib
import unittest
import os
import shutil
import json
import time

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
    'local_dir_state_path': LOCAL_DIR_STATE_FOR_TEST,
    'sharing_path': TEST_SHARING_FOLDER,
    'cmd_address': 'localhost',
    'cmd_port': 60001,
    'api_suffix': '/API/V1/',
    # no server_address to be sure
    'server_address': '',
    'user': 'user',
    'pass': 'pass',
    'activate': True,
}

# Test-user account details
USR, PW = 'user@mail.com', 'Mail_85'


def timestamp_generator():
    timestamp_generator.__test__ = False
    return long(time.time()*10000)


def create_base_dir_tree(list_of_files=LIST_OF_TEST_FILES):
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

    with open(CONFIG_FILEPATH, 'w') as f:
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
    self.operation_happened = 'move: src '+src+' dst: '+dst
    return True


def fake_make_copy(self, src, dst, timestamp):
    self.operation_happened = 'copy: src '+src+' dst: '+dst
    return True


def fake_set_cmdmanager_response(socket, message):
    response = {'message': message}
    response_packet = json.dumps(response)
    return response_packet


class TestClientDaemonConfig(unittest.TestCase):
    def setUp(self):
        create_environment()
        create_base_dir_tree()
        self.daemon = client_daemon.Daemon(CONFIG_FILEPATH, TEST_SHARING_FOLDER)

    def tearDown(self):
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

    def test_update_cfg(self):
        """
        Test updating cfg with this_is_test_value
        """
        self.daemon.cfg['this_is_test_value'] = True
        self.daemon.update_cfg()
        with open(self.daemon.CONFIG_FILEPATH, 'r') as cfg:
            self.assertTrue(json.load(cfg)['this_is_test_value'])

    def test__create_cfg_with_default_configuration(self):
        """
        Test cfg creation with default configuration.
        """
        # Set manually the configuration
        os.remove(CONFIG_FILEPATH)
        client_daemon.Daemon.CONFIG_DIR = CONFIG_DIR
        client_daemon.Daemon.CONFIG_FILEPATH = CONFIG_FILEPATH
        client_daemon.Daemon.DEF_CONF['local_dir_state_path'] = LOCAL_DIR_STATE_FOR_TEST
        client_daemon.Daemon.DEF_CONF['sharing_path'] = TEST_SHARING_FOLDER

        # Load configuration from default
        self.daemon.cfg = self.daemon._create_cfg(CONFIG_FILEPATH, TEST_SHARING_FOLDER)

        self.assertEqual(self.daemon.CONFIG_FILEPATH, CONFIG_FILEPATH)
        self.assertEqual(self.daemon.CONFIG_DIR, CONFIG_DIR)
        self.assertEqual(self.daemon.cfg['local_dir_state_path'], LOCAL_DIR_STATE_FOR_TEST)
        self.assertEqual(self.daemon.cfg['sharing_path'], TEST_SHARING_FOLDER)

    def test__create_cfg_with_custom_sharing_path(self):
        """
        Test cfg creation with custom sharing folder.
        """
        # Set manually the configuration
        os.remove(CONFIG_FILEPATH)
        client_daemon.Daemon.CONFIG_DIR = CONFIG_DIR
        client_daemon.Daemon.CONFIG_FILEPATH = CONFIG_FILEPATH
        client_daemon.Daemon.DEF_CONF['local_dir_state_path'] = LOCAL_DIR_STATE_FOR_TEST
        new_sharing_path = os.path.join(CONFIG_DIR, 'new_sharing_path')

        # Load custom configuration
        self.daemon.cfg = self.daemon._create_cfg(CONFIG_FILEPATH, new_sharing_path)

        self.assertEqual(self.daemon.cfg['sharing_path'], new_sharing_path)

    def test__create_cfg(self):
        """
        Test create cfg file with test options.
        The cfg is already created during setup, i will test the result is right.
        """
        self.assertEqual(self.daemon.CONFIG_DIR, CONFIG_DIR)
        self.assertEqual(self.daemon.CONFIG_FILEPATH, CONFIG_FILEPATH)
        self.assertEqual(self.daemon.cfg['local_dir_state_path'], LOCAL_DIR_STATE_FOR_TEST)
        self.assertEqual(self.daemon.cfg['sharing_path'], TEST_SHARING_FOLDER)

    def test__create_cfg_in_forbiden_path(self):
        """
        Test creation of cfg and cfg directory in forbidden path.
        """
        forbidden_path = '/forbiden_path/cfg_file'
        self.assertRaises(SystemExit, self.daemon._create_cfg, cfg_path=forbidden_path, sharing_path=TEST_SHARING_FOLDER)

    def test__init_sharing_path_with_default_configuration(self):
        """
        Test initialization of sharing folder with default configuration.
        """
        # Set manually the configuration
        shutil.rmtree(TEST_SHARING_FOLDER)
        client_daemon.Daemon.DEF_CONF['sharing_path'] = TEST_SHARING_FOLDER

        # Initialize configuration from default
        self.daemon._init_sharing_path(sharing_path=TEST_SHARING_FOLDER)

        with open(CONFIG_FILEPATH, 'r') as cfg:
            saved_sharing_path = json.load(cfg)['sharing_path']
        self.assertEqual(self.daemon.cfg['sharing_path'], saved_sharing_path, TEST_SHARING_FOLDER)

    def test__init_sharing_path_with_customization_folder(self):
        """
        Test Initialization of sharing folder done with customization.
        I can test this with customization happens by create_environment() during setUp.
        """
        #Create new sharing_path
        new_sharing_path= os.path.join(TEST_SHARING_FOLDER, 'test_sharing')

        # Initialize configuration with custom sharing_path
        self.daemon._init_sharing_path(sharing_path=new_sharing_path)

        with open(CONFIG_FILEPATH, 'r') as cfg:
            saved_sharing_path = json.load(cfg)['sharing_path']
        self.assertEqual(self.daemon.cfg['sharing_path'], saved_sharing_path, TEST_SHARING_FOLDER)

    def test__init_sharing_path_with_forbidden_path(self):
        """
        Test Initialization of sharing folder done with forbidden_path.
        """
        forbidden_path = '/forbidden_path/sharing_folder'
        self.assertRaises(SystemExit, self.daemon._init_sharing_path, forbidden_path)

    def test_load_cfg_with_existent_cfg(self):
        """
        This test can be done with created test environment.
        """
        self.assertEqual(self.daemon.cfg, TEST_CFG)

    def test_load_cfg_with_customization_cfg(self):
        """
        Test loading of cfg file done with customization cfg.
        """
        old_cfg = self.daemon.cfg
        os.remove(CONFIG_FILEPATH)
        self.daemon._load_cfg(cfg_path=CONFIG_FILEPATH, sharing_path=None)
        self.assertEqual(self.daemon.cfg, old_cfg)

    def test_load_cfg_from_broken_file(self):
        """
        This test load broken config file.
        We expect that default configuration is writen on file and loaded.
        """
        broken_json = '{"local_dir_state_path": LOCAL_DIR_STATE_FOR_TEST, "sharing_path": TEST_SHARING_FOLDER'

        # I expect some customize configuration is loaded
        with open(CONFIG_FILEPATH, 'w') as broken_cfg:
            broken_cfg.write(broken_json)

        self.assertNotEqual(self.daemon.cfg, client_daemon.Daemon.DEF_CONF)
        # Loading of broken_cfg
        self.daemon.cfg = self.daemon._load_cfg(cfg_path=CONFIG_FILEPATH, sharing_path=None)

        # Check what is written to the file after load, i expect that broken file is overwrited with default configuration
        with open(CONFIG_FILEPATH, 'r') as created_file:
            loaded_config = json.load(created_file)
        for cfg_line in loaded_config:
            self.assertEqual(self.daemon.cfg[cfg_line], loaded_config[cfg_line], client_daemon.Daemon.DEF_CONF[cfg_line])

    def test_load_cfg_with_missing_key(self):
        """
        This test load file cfg with missing key.
        We expect default configuration will be written on file and loaded.
        """
        # I expect some customize configuration is loaded
        missing_key_cfg = {'local_dir_state_path': 'error_value', 'missing_key': False}
        with open(CONFIG_FILEPATH, 'w') as cfg:
            json.dump(missing_key_cfg, cfg)

        self.assertNotEqual(self.daemon.cfg, client_daemon.Daemon.DEF_CONF)
        # Loading of cfg with missing key
        self.daemon.cfg = self.daemon._load_cfg(cfg_path=CONFIG_FILEPATH, sharing_path=None)

        # Check what is written to the file after load, i expect that cfg is overwrited with default configuration
        with open(CONFIG_FILEPATH, 'r') as created_file:
            loaded_config = json.load(created_file)
        for cfg_line in loaded_config:
            self.assertEqual(self.daemon.cfg[cfg_line], loaded_config[cfg_line], client_daemon.Daemon.DEF_CONF[cfg_line])
        # Check configuration inside missing_key_cfg is not written with default_cfg
        self.assertNotEqual(missing_key_cfg['local_dir_state_path'], self.daemon.cfg['local_dir_state_path'])
        self.assertNotIn('missing_key', self.daemon.cfg)

    def test_load_cfg_with_unexistent_path(self):
        """
        Test load_cfg with cfg_path of unexistent file.
        I expect default cfg is loaded.
        """
        os.remove(CONFIG_FILEPATH)

        self.assertNotEqual(self.daemon.cfg, client_daemon.Daemon.DEF_CONF)
        # Loading unexistent cfg
        self.daemon.cfg = self.daemon._load_cfg(cfg_path=CONFIG_FILEPATH, sharing_path=None)

        # Check what is written to the file after load, i expect that cfg is overwrited with default configuration
        with open(CONFIG_FILEPATH, 'r') as created_file:
            loaded_config = json.load(created_file)
        for cfg_line in loaded_config:
            self.assertEqual(self.daemon.cfg[cfg_line], loaded_config[cfg_line], client_daemon.Daemon.DEF_CONF[cfg_line])


class TestClientDaemonDirState(unittest.TestCase):
    def setUp(self):
        create_environment()
        create_base_dir_tree()
        self.daemon = client_daemon.Daemon(CONFIG_FILEPATH, TEST_SHARING_FOLDER)

    def tearDown(self):
        destroy_folder()

    def test_md5_of_client_snapshot(self):
        """
        Test MD5_OF_CLIENT_SNAPSHOT: Check the global_md5_method
        :return:
        """
        time_stamp = timestamp_generator()
        self.daemon.client_snapshot = base_dir_tree.copy()

        md5hash = hashlib.md5()

        for path, time_md5 in sorted(self.daemon.client_snapshot.iteritems()):
            # extract md5 from tuple. we don't need hexdigest it's already md5
            md5hash.update(time_md5[1])
            md5hash.update(path)

        self.daemon.md5_of_client_snapshot()
        self.assertEqual(md5hash.hexdigest(), self.daemon.md5_of_client_snapshot())

    def test_is_directory_not_modified(self):
        self.daemon.client_snapshot = base_dir_tree.copy()
        self.daemon.update_local_dir_state(timestamp_generator())

        old_global_md5 = self.daemon.local_dir_state['global_md5']
        is_dir_modified_result = self.daemon._is_directory_modified()
        test_md5 = self.daemon.local_dir_state['global_md5']

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

        self.assertEqual(self.daemon.local_dir_state['global_md5'], self.daemon.md5_of_client_snapshot(), msg='The global_md5 i save is the save i load')
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'], time_stamp, msg='The timestamp i save is the save i load')


class TestClientDaemonActions(unittest.TestCase):
    def setUp(self):
        create_environment()
        create_base_dir_tree()
        self.daemon = client_daemon.Daemon(CONFIG_FILEPATH, TEST_SHARING_FOLDER)
        self.daemon.operation_happened = 'initial'
        self.daemon.create_observer()
        self.daemon.observer.start()

    def tearDown(self):
        global base_dir_tree
        base_dir_tree = {}
        self.daemon.observer.stop()
        self.daemon.observer.join()
        destroy_folder()

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

        self.assertEqual(
            self.daemon._make_copy_on_client(file_to_be_move_not_exists, dst_file_that_not_exists, server_timestamp), False)
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

        self.assertEqual(
            self.daemon._make_move_on_client(file_to_move_exists, dst_file_that_not_exists, server_timestamp), True)
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

        self.assertEqual(
            self.daemon._make_move_on_client(file_to_be_move_not_exists, dst_file_that_not_exists, server_timestamp), False)

        # test local dir state after movement
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'], server_timestamp - 5)
        self.assertEqual(self.daemon.local_dir_state['global_md5'], self.daemon.md5_of_client_snapshot())

    def test_make_move_function_dst_file_exists(self):
        """
        Test _MAKE_MOVE: test the MOVE function when the DST EXISTS
        :return:
        """
        create_base_dir_tree(['file1.txt', 'move_folder/file1.txt'])
        self.daemon.client_snapshot = base_dir_tree.copy()

        # Create the files in client_snapshot / base_dir_tree
        create_files(self.daemon.client_snapshot)
        server_timestamp = timestamp_generator()
        file_to_move = 'file1.txt'
        dst_file_exists = 'move_folder/file1.txt'

        self.assertEqual(self.daemon._make_move_on_client(file_to_move, dst_file_exists, server_timestamp), True)


class TestClientDaemonSync(unittest.TestCase):
    def setUp(self):
        create_environment()
        create_base_dir_tree()
        self.daemon = client_daemon.Daemon(CONFIG_FILEPATH, TEST_SHARING_FOLDER)
        self.daemon.operation_happened = 'initial'
        self.daemon.create_observer()
        self.daemon.observer.start()

    def tearDown(self):
        global base_dir_tree
        base_dir_tree = {}
        self.daemon.observer.stop()
        self.daemon.observer.join()
        destroy_folder()

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

        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree), [])
        self.assertEqual(self.daemon.operation_happened, 'move: src '+src+' dst: '+dst)

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

        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree), [])
        self.assertEqual(self.daemon.operation_happened, 'copy: src '+src+' dst: '+dst)

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
                         [('download', 'new_file_on_server.txt')])
        # Local Directory is NOT MODIFIED
        self.assertEqual(new_global_md5_client, old_global_md5_client)

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
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp - 1, 'global_md5': old_global_md5_client}

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
        self.daemon = client_daemon.Daemon(CONFIG_FILEPATH, TEST_SHARING_FOLDER)
        self.daemon.create_observer()
        self.daemon.observer.start()
        self.daemon.cfg['user'] = ''
        self.daemon.cfg['pass'] = ''
        self.daemon.cfg['activate'] = False
        self.socket = test_utils.FakeSocket()

    def tearDown(self):
        self.daemon.observer.stop()
        self.daemon.observer.join()

    def test_get_cmdmanager_request(self):
        command = {'shutdown': ()}
        json_data = json.dumps(command)
        self.socket.set_response(json_data)

        self.assertEquals(self.daemon._get_cmdmanager_request(self.socket), json.loads(json_data))

    def test_set_cmdmanager_response(self):
        response = 'testtestetst'
        self.assertEqual(self.daemon._set_cmdmanager_response(self.socket, response), json.dumps({'message': response}))

    def test__activation_check_block_not_allowed_operation(self):
        """
        Test that _activation_check block not allowed operation
        """
        def fake_initialize_observing():
            function_called = True

        function_called = False
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response
        self.daemon._initialize_observing = fake_initialize_observing

        command = 'not_allowed'
        data = {}
        old_user = self.daemon.cfg['user']
        old_pass = self.daemon.cfg['pass']
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with not allowed operation
        self.daemon._activation_check(self.socket, command, data)

        self.assertEqual(old_user, self.daemon.cfg['user'])
        self.assertEqual(old_pass, self.daemon.cfg['pass'])
        self.assertFalse(old_activate_state, self.daemon.cfg['activate'])

        # Test the observing is not started
        self.assertFalse(function_called)

    def test__activation_check_receive_registration_cmd_with_success(self):
        """
        Test that _activation_check receive registration cmd and registration is successful.
        """
        def fake_initialize_observing():
            self.init_observing_called = True

        def fake_register_into_connection_manager(data):
            return {'successful': True}

        self.init_observing_called = False
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response
        self.daemon._initialize_observing = fake_initialize_observing

        command = 'register'
        self.daemon.conn_mng.do_register = fake_register_into_connection_manager

        data = (USR, PW)
        old_user = self.daemon.cfg['user']
        old_pass = self.daemon.cfg['pass']
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with successful response from server
        self.daemon._activation_check(self.socket, command, data)

        self.assertEqual(self.daemon.cfg['user'], USR)
        self.assertNotEqual(self.daemon.cfg['user'], old_user)
        self.assertEqual(self.daemon.cfg['pass'], PW)
        self.assertNotEqual(self.daemon.cfg['pass'], old_pass)
        self.assertFalse(old_activate_state, self.daemon.cfg['activate'])

        # Test the observing is not started
        self.assertFalse(self.init_observing_called)

    def test__activation_check_receive_registration_cmd_with_failed_registration_on_server(self):
        """
#       Test that _activation_check receive registration cmd and registration failed on server.
        """
        def fake_initialize_observing():
            self.init_observing_called = True

        def fake_register_into_connection_manager(data):
            return {'successful': False}

        self.init_observing_called = False
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response
        self.daemon._initialize_observing = fake_initialize_observing

        command = 'register'
        self.daemon.conn_mng.do_register = fake_register_into_connection_manager

        data = (USR, PW)
        old_user = self.daemon.cfg['user']
        old_pass = self.daemon.cfg['pass']
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with failed response from server
        self.daemon._activation_check(self.socket, command, data)

        self.assertEqual(old_user, self.daemon.cfg['user'])
        self.assertEqual(old_pass, self.daemon.cfg['pass'])
        self.assertFalse(old_activate_state, self.daemon.cfg['activate'])

        # Test the observing is not started
        self.assertFalse(self.init_observing_called)

    def test__activation_check_receive_activation_cmd_with_success(self):
        """
        Test that _activation_check receive registration cmd and registration is successful.
        """
        def fake_initialize_observing():
            self.init_observing_called = True

        def fake_activation_into_connection_manager(data):
            return {'successful': True}

        self.init_observing_called = False
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response
        self.daemon._initialize_observing = fake_initialize_observing

        command = 'activate'
        self.daemon.conn_mng.do_activate = fake_activation_into_connection_manager

        data = (USR, 'token_authorized')
        old_user = self.daemon.cfg['user'] = USR
        old_pass = self.daemon.cfg['pass'] = PW
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with successful response from server
        self.daemon._activation_check(self.socket, command, data)

        self.assertEqual(self.daemon.cfg['user'], USR, old_user)
        self.assertEqual(self.daemon.cfg['pass'], PW, old_pass)
        self.assertTrue(self.daemon.cfg['activate'])
        self.assertNotEqual(self.daemon.cfg['activate'], old_activate_state)

        # Test the observing is started
        self.assertTrue(self.init_observing_called)


if __name__ == '__main__':
    unittest.main()
