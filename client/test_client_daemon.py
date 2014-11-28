#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hashlib
import unittest
import os
import shutil
import json
import time

import client_daemon
import tstutils

from contextlib import contextmanager

#########################################################################################
# This setting allow to silence client_daemon test, if u need to see all the log message
# put the level at DEBUG level: --> client_daemon.logger.setLevel(DEBUG)
from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG
client_daemon.logger.setLevel(CRITICAL)
#########################################################################################

# Don't change this setting! This line avoid to write on log file during test
client_daemon.file_handler.setLevel(CRITICAL)

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

LIST_OF_TEST_SHARED_FILES = [
    'shared/user1/file1.txt',
    'shared/user1/file2.dat',
    'shared/pysqualo/file1.txt',
    'shared/jacopyno/file2.dat',
    'shared/milly/folder/file.txt',
    'shared/millino/folder/filefile.dat',
    'shared/millito/jacopo.txt',
    'shared/utente/graphics.psd',

]

base_dir_tree = {}
shared_files_dir_tree = {}

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


def fake_hash_file(file_path, chunk_size=1024):
    return 'test'


def fake_search_md5(searched_md5):
    return None


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


def create_shared_files_dir_tree(files=LIST_OF_TEST_SHARED_FILES):
    global shared_files_dir_tree
    shared_files_dir_tree = {}
    for path in files:
        time_stamp = timestamp_generator()
        md5 = hashlib.md5(path).hexdigest()
        shared_files_dir_tree[path] = [time_stamp, md5]


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


def fake_make_move(self, src, dst):

    self.operation_happened = "move: src "+src+" dst: "+dst
    return True


def fake_make_copy(self, src, dst):

    self.operation_happened = "copy: src "+src+" dst: "+dst
    return True


def fake_set_cmdmanager_response(socket, message):
    response = {'message': message}
    response_packet = json.dumps(response)
    return response_packet


class FakeConnMng(object):

    def __init__(self):
        self.called_cmd = ''
        self.received_data = ''

    def dispatch_request(self, cmd, data):
        self.called_cmd = cmd
        self.received_data = data
        return {'content': {'server_timestamp': time.time()*10000}, 'successful': True}


class FileFakeEvent(object):
    """
    Class that simulates a file related event sent from watchdog.
    Actually create <src_path> and <dest_path> attributes and the file on disk.
    """
    def __init__(self, src_path, src_content='', dest_path=None, dest_content=''):
        self.src_path = src_path
        self.dest_path = dest_path
        if src_content:
            self.create_file(src_path, content=src_content)
        if dest_content:
            self.create_file(dest_path, content=dest_content)
        self.is_directory = False

    def create_file(self, path, content=''):
        path_dir = os.path.dirname(path)
        if not os.path.exists(path_dir):
            os.makedirs(path_dir)
        with open(path, 'w') as f:
            f.write(content)


class TestClientDaemonConfig(unittest.TestCase):
    def setUp(self):
        create_environment()
        create_base_dir_tree()
        create_shared_files_dir_tree()
        self.daemon = client_daemon.Daemon(CONFIG_FILEPATH, TEST_SHARING_FOLDER)

    def tearDown(self):

        global base_dir_tree, shared_files_dir_tree
        base_dir_tree = {}
        shared_files_dir_tree = {}
        destroy_folder()

    def test__build_directory(self):
        """
        Create directory
        :return: boolean value, True is created or already existent
        """
        self.assertTrue(self.daemon._build_directory('cartella_di_prova'))
        self.assertTrue(self.daemon._build_directory('cartella_di_prova'))

    def test__build_directory_in_forbidden_path(self):
        """
        Create directory in forbidden path
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

    def test__create_cfg_in_forbidden_path(self):
        """
        Test creation of cfg and cfg directory in forbidden path.
        """
        forbidden_path = '/forbidden_path/cfg_file'
        self.assertRaises(SystemExit, self.daemon._create_cfg, cfg_path=forbidden_path,
                          sharing_path=TEST_SHARING_FOLDER)

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
        new_sharing_path = os.path.join(TEST_SHARING_FOLDER, 'test_sharing')

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
        We expect that default configuration is written on file and loaded.
        """
        broken_json = '{"local_dir_state_path": LOCAL_DIR_STATE_FOR_TEST, "sharing_path": TEST_SHARING_FOLDER'

        # I expect some customize configuration is loaded
        with open(CONFIG_FILEPATH, 'w') as broken_cfg:
            broken_cfg.write(broken_json)

        self.assertNotEqual(self.daemon.cfg, client_daemon.Daemon.DEF_CONF)
        # Loading of broken_cfg
        self.daemon.cfg = self.daemon._load_cfg(cfg_path=CONFIG_FILEPATH, sharing_path=None)

        # Check what is written to the file after load, i expect that broken file is overwrited with default config
        with open(CONFIG_FILEPATH, 'r') as created_file:
            loaded_config = json.load(created_file)
        for cfg_line in loaded_config:
            self.assertEqual(self.daemon.cfg[cfg_line], loaded_config[cfg_line],
                             client_daemon.Daemon.DEF_CONF[cfg_line])

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

        # Check what is written to the file after load, i expect that cfg is overwritten with default configuration
        with open(CONFIG_FILEPATH, 'r') as created_file:
            loaded_config = json.load(created_file)
        for cfg_line in loaded_config:
            self.assertEqual(self.daemon.cfg[cfg_line], loaded_config[cfg_line],
                             client_daemon.Daemon.DEF_CONF[cfg_line])
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

        # Check what is written to the file after load, i expect that cfg is overwritten with default configuration
        with open(CONFIG_FILEPATH, 'r') as created_file:
            loaded_config = json.load(created_file)
        for cfg_line in loaded_config:
            self.assertEqual(self.daemon.cfg[cfg_line], loaded_config[cfg_line],
                             client_daemon.Daemon.DEF_CONF[cfg_line])


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

        self.assertEqual(self.daemon.local_dir_state['global_md5'], self.daemon.md5_of_client_snapshot(),
                         msg="The global_md5 i save is the save i load")
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'], time_stamp,
                         msg="The timestamp i save is the save i load")


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
        # Create the files in client_snapshot / base_dir_tree
        create_files(self.daemon.client_snapshot)

        file_to_copy = 'file1.txt'
        dst_file_of_copy = 'fake2/copy_file1.txt'

        self.assertTrue(self.daemon._make_copy_on_client(file_to_copy, dst_file_of_copy))

        self.assertIn(dst_file_of_copy, self.daemon.client_snapshot)

    def test_make_copy_not_src(self):
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
            self.daemon._make_copy_on_client(file_to_be_move_not_exists, dst_file_that_not_exists), False)
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

        # Create the files in client_snapshot / base_dir_tree
        create_files(self.daemon.client_snapshot)

        file_to_move_exists = 'file1.txt'
        dst_file_that_not_exists = 'fake2/move_file1.txt'

        self.assertTrue(self.daemon._make_move_on_client(file_to_move_exists, dst_file_that_not_exists))
        self.assertIn(dst_file_that_not_exists, self.daemon.client_snapshot)


    def test_make_move_function_not_src(self):
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
            self.daemon._make_move_on_client(file_to_be_move_not_exists, dst_file_that_not_exists), False)

        # test local dir state after movement
        self.assertEqual(self.daemon.local_dir_state['last_timestamp'], server_timestamp - 5)
        self.assertEqual(self.daemon.local_dir_state['global_md5'], self.daemon.md5_of_client_snapshot())

    def test_make_move_function_not_dst(self):
        """
        Test _MAKE_MOVE: test the MOVE function when the DST EXISTS
        :return:
        """
        create_base_dir_tree(['file1.txt', 'move_folder/file1.txt'])
        self.daemon.client_snapshot = base_dir_tree.copy()

        # Create the files in client_snapshot / base_dir_tree
        create_files(self.daemon.client_snapshot)
        file_to_move = 'file1.txt'
        dst_file_exists = 'move_folder/file1.txt'

        self.assertEqual(self.daemon._make_move_on_client(file_to_move, dst_file_exists), True)


class TestClientDaemonSync(unittest.TestCase):
    def setUp(self):
        create_environment()
        create_base_dir_tree()
        create_shared_files_dir_tree()
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

    def test_sync_process_new_on_both(self):
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
                         [('download', 'new_file_on_server.txt'), ('upload', 'new_file_on_client.txt')])

        # Local Directory is MODIFIED
        self.assertNotEqual(new_global_md5_client, old_global_md5_client)

    def test_sync_process_modified_on_both(self):
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

        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree), [('modify', 'file.txt')])

        # Local Directory is MODIFIED
        self.assertNotEqual(new_global_md5_client, old_global_md5_client)

########################SHARED FILES TESTING#####################################################################
    def test__read_only_shared_folder_new_file(self):
        """
        Test SYNC: Test the case when the user create a new file in a shared path (read-only)
        it must ignore the tracking of file and it mustn't synchronize with the server
        """

        #setup the mock

        server_timestamp = timestamp_generator()

        # server tree and client tree starting with the same situation
        server_dir_tree = shared_files_dir_tree.copy()
        server_dir_tree.update(base_dir_tree.copy())
        self.daemon.shared_snapshot = shared_files_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()

        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # client timestamp = server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp, 'global_md5': old_global_md5_client}

        new_file_path = os.path.join(TEST_SHARING_FOLDER, 'shared/test/new_file.txt')
        event = FileFakeEvent(new_file_path)
        self.daemon.conn_mng = FakeConnMng()
        self.daemon.search_md5 = fake_search_md5
        self.daemon.hash_file = fake_hash_file

        # test
        self.daemon.on_created(event)

        self.assertEqual(self.daemon.shared_snapshot, shared_files_dir_tree)
        self.assertEqual(self.daemon.client_snapshot, base_dir_tree)

    def test__read_only_shared_folder_move_file_from_shared_to_not_shared(self):
        """
        Test SYNC: Test the case when the user moves a file from a shared path to a not shared path (read-only)

        """

        #setup the mock

        server_timestamp = timestamp_generator()

        # server tree and client tree starting with the same situation
        server_dir_tree = shared_files_dir_tree.copy()
        server_dir_tree.update(base_dir_tree.copy())
        self.daemon.shared_snapshot = shared_files_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()

        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # client timestamp = server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp, 'global_md5': old_global_md5_client}

        source_file_path = os.path.join(TEST_SHARING_FOLDER, 'shared/user1/file1.txt')
        dest_file_path = os.path.join(TEST_SHARING_FOLDER, 'new_file.txt')
        event = FileFakeEvent(source_file_path, dest_path=dest_file_path)
        self.daemon.conn_mng = FakeConnMng()
        self.daemon.hash_file = fake_hash_file

        # test
        expected_shared_snapshop = self.daemon.shared_snapshot.copy()
        expected_shared_snapshop.pop('shared/user1/file1.txt')

        self.daemon.on_moved(event)

        self.assertEqual(self.daemon.shared_snapshot, expected_shared_snapshop)
        self.assertIn('new_file.txt', self.daemon.client_snapshot)

    def test__read_only_shared_folder_move_file_from_shared_to_shared(self):
        """
        Test SYNC: Test the case when the user moves a file from a shared path to a shared path (read-only)

        """

        # setup the mock

        server_timestamp = timestamp_generator()

        # server tree and client tree starting with the same situation
        server_dir_tree = shared_files_dir_tree.copy()
        server_dir_tree.update(base_dir_tree.copy())
        self.daemon.shared_snapshot = shared_files_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()

        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # client timestamp = server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp, 'global_md5': old_global_md5_client}

        source_file_path = os.path.join(TEST_SHARING_FOLDER, 'shared/user1/file1.txt')
        dest_file_path = os.path.join(TEST_SHARING_FOLDER, 'shared/test/new_file.txt')
        event = FileFakeEvent(source_file_path, dest_path=dest_file_path)
        self.daemon.conn_mng = FakeConnMng()
        self.daemon.hash_file = fake_hash_file

        # test the case the dest_file_path it' a new path
        self.daemon.on_moved(event)

        expected_shared_snapshop = shared_files_dir_tree.copy()
        expected_shared_snapshop.pop('shared/user1/file1.txt')

        self.assertEqual(self.daemon.shared_snapshot, expected_shared_snapshop)
        self.assertEqual(self.daemon.client_snapshot, base_dir_tree)


        # setup the mock
        source_file_path = os.path.join(TEST_SHARING_FOLDER, 'shared/user1/file1.txt')
        dest_file_path = os.path.join(TEST_SHARING_FOLDER, 'shared/millino/folder/filefile.dat')
        event = FileFakeEvent(source_file_path, dest_path=dest_file_path)
        self.daemon.conn_mng = FakeConnMng()
        self.daemon.hash_file = fake_hash_file

        # test the case the dest_file_path already exist so it means that old file is modified
        self.daemon.on_moved(event)

        expected_shared_snapshop = shared_files_dir_tree.copy()
        expected_shared_snapshop.pop('shared/user1/file1.txt')
        expected_shared_snapshop.pop('shared/millino/folder/filefile.dat')

        self.assertEqual(self.daemon.shared_snapshot, expected_shared_snapshop)
        self.assertEqual(self.daemon.client_snapshot, base_dir_tree)

    def test__read_only_shared_folder_move_file_from_not_shared_to_shared(self):
        """
        Test SYNC: Test the case when the user moves a file from a not shared path to a shared path (read-only)

        """

        # setup the mock

        server_timestamp = timestamp_generator()

        # server tree and client tree starting with the same situation
        server_dir_tree = shared_files_dir_tree.copy()
        server_dir_tree.update(base_dir_tree.copy())
        self.daemon.shared_snapshot = shared_files_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()

        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # client timestamp = server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp, 'global_md5': old_global_md5_client}

        source_file_path = os.path.join(TEST_SHARING_FOLDER, 'file1.txt')
        dest_file_path = os.path.join(TEST_SHARING_FOLDER, 'shared/test/new_file.txt')
        event = FileFakeEvent(source_file_path, dest_path=dest_file_path)
        self.daemon.conn_mng = FakeConnMng()
        self.daemon.hash_file = fake_hash_file

        # test the case the dest_file_path it' a new path
        self.daemon.on_moved(event)

        expected_client_snapshop = base_dir_tree.copy()
        expected_client_snapshop.pop('file1.txt')

        self.assertEqual(self.daemon.client_snapshot, expected_client_snapshop)
        self.assertEqual(self.daemon.shared_snapshot, shared_files_dir_tree)


        # setup the mock
        source_file_path = os.path.join(TEST_SHARING_FOLDER, 'file1.txt')
        dest_file_path = os.path.join(TEST_SHARING_FOLDER, 'shared/millino/folder/filefile.dat')
        event = FileFakeEvent(source_file_path, dest_path=dest_file_path)
        self.daemon.conn_mng = FakeConnMng()
        self.daemon.hash_file = fake_hash_file

        # test the case the dest_file_path already exist so it means that old file is modified
        self.daemon.on_moved(event)

        expected_shared_snapshop = shared_files_dir_tree.copy()
        expected_shared_snapshop.pop('shared/millino/folder/filefile.dat')
        expected_client_snapshop = base_dir_tree.copy()
        expected_client_snapshop.pop('file1.txt')

        self.assertEqual(self.daemon.shared_snapshot, expected_shared_snapshop)
        self.assertEqual(self.daemon.client_snapshot, expected_client_snapshop)

    def test__read_only_shared_folder_file_modified(self):
        """
        Test SYNC: Test the case when the user modify a file in shared folder

        """

        # setup the mock

        server_timestamp = timestamp_generator()

        # server tree and client tree starting with the same situation
        server_dir_tree = shared_files_dir_tree.copy()
        server_dir_tree.update(base_dir_tree.copy())
        self.daemon.shared_snapshot = shared_files_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()

        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # client timestamp = server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp, 'global_md5': old_global_md5_client}

        source_file_path = os.path.join(TEST_SHARING_FOLDER, 'shared/user1/file1.txt')
        event = FileFakeEvent(source_file_path)

        self.daemon.conn_mng = FakeConnMng()
        self.daemon.hash_file = fake_hash_file

        # test
        self.daemon.on_modified(event)

        expected_shared_snapshop = shared_files_dir_tree.copy()
        expected_shared_snapshop.pop('shared/user1/file1.txt')

        self.assertEqual(self.daemon.client_snapshot, base_dir_tree)
        self.assertEqual(self.daemon.shared_snapshot, expected_shared_snapshop)

    def test__read_only_shared_folder_file_deleted(self):
        """
        Test SYNC: Test the case when the user removes a file from shared folder

        """

        # setup the mock

        server_timestamp = timestamp_generator()

        # server tree and client tree starting with the same situation
        server_dir_tree = shared_files_dir_tree.copy()
        server_dir_tree.update(base_dir_tree.copy())
        self.daemon.shared_snapshot = shared_files_dir_tree.copy()
        self.daemon.client_snapshot = base_dir_tree.copy()
        old_global_md5_client = self.daemon.md5_of_client_snapshot()

        # client timestamp = server_timestamp
        self.daemon.local_dir_state = {'last_timestamp': server_timestamp, 'global_md5': old_global_md5_client}

        source_file_path = os.path.join(TEST_SHARING_FOLDER, 'shared/user1/file1.txt')
        event = FileFakeEvent(source_file_path)

        self.daemon.conn_mng = FakeConnMng()
        self.daemon.hash_file = fake_hash_file

        # test
        self.daemon.on_deleted(event)


        expected_shared_snapshop = shared_files_dir_tree.copy()
        expected_shared_snapshop.pop('shared/user1/file1.txt')

        self.assertEqual(self.daemon.client_snapshot, base_dir_tree)
        self.assertEqual(self.daemon.shared_snapshot, expected_shared_snapshop)

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

    def test_sync_process_ts_equal(self):
        """
        Test SYNC: server_timestamp == client_timestamp
        local dir is MODIFIED
        files in server but not in client: delete on server
        """

        create_base_dir_tree(['file_test.txt'])
        server_timestamp = timestamp_generator()

        # Server and client are the same
        self.daemon.client_snapshot = base_dir_tree.copy()
        server_dir_tree = base_dir_tree.copy()

        # server ts and client ts are the same
        self.daemon.local_dir_state['last_timestamp'] = server_timestamp
        # directory not modified
        self.daemon.local_dir_state['global_md5'] = self.daemon.md5_of_client_snapshot()

        # dir is now modified with this two operations
        self.daemon.client_snapshot['file.txt'] = (server_timestamp - 1, '321456879')
        self.daemon.client_snapshot['file_test.txt'] = (server_timestamp - 1, '123654789')

        # add a file with timestamp < client_timestamp
        server_dir_tree.update({'new_file_on_server': (server_timestamp - 2, 'md5md6jkshkfv')})

        # files in server but not in client,
        # local_dir is modified,
        # client_ts == server_ts
        # test the delete of new_file_on_server
        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
                         [('delete', 'new_file_on_server'), ('modify', 'file_test.txt'), ('upload', 'file.txt')])

    def mock_move_on_client(self, src, dst):

        self.daemon.client_snapshot[dst] = self.daemon.client_snapshot[src]
        self.daemon.client_snapshot.pop(src)
        return True

    def mock_copy_on_client(self, src, dst):

        self.daemon.client_snapshot[dst] = self.daemon.client_snapshot[src]
        return True

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
        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree), [('upload', 'new_file_')])

        # assure the move
        self.assertIn('folder/file_test_moved.txt', self.daemon.client_snapshot)
        self.assertNotIn('file_test_move.txt', self.daemon.client_snapshot)

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
        file_md5 = '987654321'
        self.daemon.client_snapshot['file_test_copy.txt'] = (server_timestamp - 1, file_md5)
        server_dir_tree['file_test_copy.txt'] = (server_timestamp - 1, file_md5)

        # copied file on server must be copied on client now
        server_dir_tree['file_test_copied.txt'] = (server_timestamp, file_md5)

        # server_ts > client_ts
        self.daemon.local_dir_state['last_timestamp'] = server_timestamp - 5
        self.daemon.local_dir_state['global_md5'] = self.daemon.md5_of_client_snapshot()

        # adding file to client_snapshot so dir will be  modified
        new_file_md5 = '645987123'
        self.daemon.client_snapshot['another_file_modified.txt'] = (server_timestamp - 1, new_file_md5)

        # mock the function. if not it will try to really move the file on disk
        self.daemon._make_copy_on_client = self.mock_copy_on_client

        # dir is modified so i've to find an upload
        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree),
                         [('upload', 'another_file_modified.txt')])

        # the file copied must be in the client snapshot after the copy
        self.assertIn('file_test_copied.txt', self.daemon.client_snapshot)
        self.assertIn('file_test_copy.txt', self.daemon.client_snapshot)

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
        self.assertEqual(self.daemon._sync_process(server_timestamp, server_dir_tree), [('upload', expected_value)])

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

    ################ TEST EVENTS ####################

    def test_on_modified(self):
        """"
        Test EVENTS: test on modified event of watchdog, expect a modify requests
        """
        filename = 'file.txt'
        src_filepath = os.path.join(TEST_SHARING_FOLDER, filename)
        old_content = 'old content of file'
        old_content_md5 = hashlib.md5(old_content).hexdigest()
        new_content = 'new content of file'
        new_content_md5 = hashlib.md5(new_content).hexdigest()
        received_data = {'filepath': filename, 'md5': new_content_md5}
        # replace connection manager in the client instance
        with replace_conn_mng(self.daemon, FakeConnMng()):
            # Initialize client_snapshot
            create_base_dir_tree([])
            global base_dir_tree
            base_dir_tree[filename] = [time.time()*10000, old_content_md5]
            self.daemon.client_snapshot = base_dir_tree.copy()
            # Check initial state
            self.assertIn(filename, self.daemon.client_snapshot)
            self.assertIn(old_content_md5, self.daemon.client_snapshot[filename])
            # Load event
            self.daemon.on_modified(FileFakeEvent(src_path=src_filepath, src_content=new_content))
            self.assertEqual(self.daemon.conn_mng.called_cmd, 'modify')
            self.assertEqual(self.daemon.conn_mng.received_data, received_data)
            # Check state after event
            self.assertIn(filename, self.daemon.client_snapshot)
            self.assertIn(new_content_md5, self.daemon.client_snapshot[filename])

    def test_on_deleted(self):
        """"
        Test EVENTS: test on deleted event of watchdog, expect a delete requests
        """
        filename = 'file.txt'
        src_filepath = os.path.join(TEST_SHARING_FOLDER, filename)
        content = 'content of file'
        content_md5 = hashlib.md5(content).hexdigest()
        received_data = {'filepath': filename}
        # replace connection manager in the client instance
        with replace_conn_mng(self.daemon, FakeConnMng()):
            # Initialize client_snapshot
            create_base_dir_tree([])
            global base_dir_tree
            base_dir_tree[filename] = [time.time()*10000, content_md5]
            self.daemon.client_snapshot = base_dir_tree.copy()
            # Check initial state
            self.assertIn(filename, self.daemon.client_snapshot)
            # Load event
            self.daemon.on_deleted(FileFakeEvent(src_path=src_filepath, src_content=content_md5))
            self.assertEqual(self.daemon.conn_mng.called_cmd, 'delete')
            self.assertEqual(self.daemon.conn_mng.received_data, received_data)
            # Check state after event
            self.assertNotIn(filename, self.daemon.client_snapshot)

    def test_on_created(self):
        """"
        Test EVENTS: test on created event of watchdog, expect a upload requests
        """
        filename = 'file.txt'
        src_filepath = os.path.join(TEST_SHARING_FOLDER, filename)
        content = 'content of file'
        content_md5 = hashlib.md5(content).hexdigest()
        received_data = {'filepath': filename, 'md5': content_md5}
        # replace connection manager in the client instance
        with replace_conn_mng(self.daemon, FakeConnMng()):
            # Initialize client_snapshot
            create_base_dir_tree([])
            self.daemon.client_snapshot = base_dir_tree.copy()
            # Check initial state
            self.assertNotIn(filename, self.daemon.client_snapshot)
            # Load event
            self.daemon.on_created(FileFakeEvent(src_path=src_filepath, src_content=content))
            self.assertEqual(self.daemon.conn_mng.called_cmd, 'upload')
            self.assertEqual(self.daemon.conn_mng.received_data, received_data)
            # Check state after event
            self.assertIn(filename, self.daemon.client_snapshot)

    def test_modify_event_from_on_created_event(self):
        """"
        Test EVENTS: test on created event of watchdog, expect a modify requests
        """
        filename = 'file.txt'
        src_filepath = os.path.join(TEST_SHARING_FOLDER, filename)
        old_content = 'old content of file'
        old_content_md5 = hashlib.md5(old_content).hexdigest()
        new_content = 'new content of file'
        new_content_md5 = hashlib.md5(new_content).hexdigest()
        received_data = {'filepath': filename, 'md5': new_content_md5}
        # replace connection manager in the client instance
        with replace_conn_mng(self.daemon, FakeConnMng()):
            # Initialize client_snapshot
            create_base_dir_tree([])
            global base_dir_tree
            base_dir_tree[filename] = [time.time()*10000, old_content_md5]
            self.daemon.client_snapshot = base_dir_tree.copy()
            # Check initial state
            self.assertIn(filename, self.daemon.client_snapshot)
            self.assertIn(old_content_md5, self.daemon.client_snapshot[filename])
            # Load event
            self.daemon.on_created(FileFakeEvent(src_path=src_filepath, src_content=new_content))
            self.assertEqual(self.daemon.conn_mng.called_cmd, 'modify')
            self.assertEqual(self.daemon.conn_mng.received_data, received_data)
            # Check state after event
            self.assertIn(filename, self.daemon.client_snapshot)
            self.assertIn(new_content_md5, self.daemon.client_snapshot[filename])

    def test_on_copy_event_inside_create_event(self):
        """"
        Test EVENTS: test on created event of watchdog, expect a copy requests
        on_created event must be detected as a copy event when a file
        with the same md5 is already in the client_snapshot
        """

        src_filename = 'a_file.txt'
        dst_filename = 'folder/b_file.txt'
        dest_filepath = os.path.join(TEST_SHARING_FOLDER, dst_filename)
        content = 'content of file'
        content_md5 = hashlib.md5(content).hexdigest()
        received_data = {'src': src_filename, 'dst': dst_filename, 'md5': content_md5}
        # replace connection manager in the client instance
        with replace_conn_mng(self.daemon, FakeConnMng()):
            # Initialize client_snapshot
            create_base_dir_tree([])
            global base_dir_tree
            base_dir_tree[src_filename] = [time.time()*10000, content_md5]
            self.daemon.client_snapshot = base_dir_tree.copy()
            # Check initial state
            self.assertIn(src_filename, self.daemon.client_snapshot)
            self.assertNotIn(dst_filename, self.daemon.client_snapshot)
            # Load event
            # I will put dest_filepath in e.src_path because watchdog see copy event as create of new file.
            # During on_created method the program check if exist a src_path with the same md5
            self.daemon.on_created(FileFakeEvent(src_path=dest_filepath, src_content=content))
            self.assertEqual(self.daemon.conn_mng.called_cmd, 'copy')
            self.assertEqual(self.daemon.conn_mng.received_data, received_data)
            # Check state after event
            self.assertIn(src_filename, self.daemon.client_snapshot)
            self.assertIn(dst_filename, self.daemon.client_snapshot)

    def test_on_moved(self):
        """
        Test EVENTS: test on moved event of watchdog, expect a move requests
        """
        src_filename = 'a_file.txt'
        dst_filename = 'folder/a_file.txt'
        src_filepath = os.path.join(TEST_SHARING_FOLDER, src_filename)
        dest_filepath = os.path.join(TEST_SHARING_FOLDER, dst_filename)
        content = 'content of file'
        content_md5 = hashlib.md5(content).hexdigest()
        received_data = {'src': src_filename, 'dst': dst_filename, 'md5': content_md5}
        # replace connection manager in the client instance
        with replace_conn_mng(self.daemon, FakeConnMng()):
            # Initialize client_snapshot
            create_base_dir_tree([])
            global base_dir_tree
            base_dir_tree[src_filename] = [time.time()*10000, content_md5]
            self.daemon.client_snapshot = base_dir_tree.copy()
            # Check initial state
            self.assertIn(src_filename, self.daemon.client_snapshot)
            self.assertNotIn(dst_filename, self.daemon.client_snapshot)
            # Load event
            self.daemon.on_moved(FileFakeEvent(src_path=src_filepath, dest_path=dest_filepath,
                                               dest_content=content))
            self.assertEqual(self.daemon.conn_mng.called_cmd, 'move')
            self.assertEqual(self.daemon.conn_mng.received_data, received_data)
            # Check state after event
            self.assertNotIn(src_filename, self.daemon.client_snapshot)
            self.assertIn(dst_filename, self.daemon.client_snapshot)

    def test_on_copy_event_inside_move_event(self):
        """
        Test EVENTS: test on move event of watchdog, expect a copy requests
        on_move event must be detected as a copy event when the origin path
        exist after the move event
        """
        src_filename = 'a_file.txt'
        dst_filename = 'folder/a_file.txt'
        src_filepath = os.path.join(TEST_SHARING_FOLDER, src_filename)
        dest_filepath = os.path.join(TEST_SHARING_FOLDER, dst_filename)
        content = 'content of file'
        content_md5 = hashlib.md5(content).hexdigest()
        received_data = {'src': src_filename, 'dst': dst_filename, 'md5': content_md5}
        # replace connection manager in the client instance
        with replace_conn_mng(self.daemon, FakeConnMng()):
            # Initialize client_snapshot
            create_base_dir_tree([])
            global base_dir_tree
            base_dir_tree[src_filename] = [time.time()*10000, content_md5]
            self.daemon.client_snapshot = base_dir_tree.copy()
            # Check initial state
            self.assertIn(src_filename, self.daemon.client_snapshot)
            self.assertNotIn(dst_filename, self.daemon.client_snapshot)
            # Load event
            self.daemon.on_moved(FileFakeEvent(src_path=src_filepath, src_content=content,
                                               dest_path=dest_filepath, dest_content=content))
            self.assertEqual(self.daemon.conn_mng.called_cmd, 'copy')
            self.assertEqual(self.daemon.conn_mng.received_data, received_data)
            # Check state after event
            self.assertIn(src_filename, self.daemon.client_snapshot)
            self.assertIn(dst_filename, self.daemon.client_snapshot)


@contextmanager
def replace_conn_mng(daemon, fake):
    original, daemon.conn_mng = daemon.conn_mng, fake
    yield
    daemon.conn_mng = original


class TestDaemonCmdManagerConnection(unittest.TestCase):
    def setUp(self):
        self.daemon = client_daemon.Daemon(CONFIG_FILEPATH, TEST_SHARING_FOLDER)
        self.daemon.create_observer()
        self.daemon.observer.start()
        self.daemon.cfg['user'] = ''
        self.daemon.password = ''
        self.daemon.cfg['activate'] = False

        self.socket = tstutils.FakeSocket()
        # Mocking the observing method
        self.daemon._initialize_observing = self.fake_initialize_observing
        self.init_observing_called = False

    def tearDown(self):
        self.daemon.observer.stop()
        self.daemon.observer.join()

    def fake_initialize_observing(self):
        """
        Mocking _initialize_observing,
        """
        self.init_observing_called = True

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
        #Mocking the communication with cmdmanager
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response

        command = 'not_allowed'
        data = {}
        old_user = self.daemon.cfg['user']
        old_pass = self.daemon.password
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with not allowed operation
        self.daemon._activation_check(self.socket, command, data)

        self.assertEqual(old_user, self.daemon.cfg['user'])
        self.assertEqual(old_pass, self.daemon.password)
        self.assertFalse(old_activate_state, self.daemon.cfg['activate'])

        # Test the observing is not started
        self.assertFalse(self.init_observing_called)

    def test__activation_check_receive_registration_cmd_with_success(self):
        """
        Test that _activation_check receive registration cmd and registration is successful.
        """
        def fake_register_into_connection_manager(data):
            return {'successful': True}

        #Mocking the communication with cmdmanager
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response

        command = 'register'
        self.daemon.conn_mng.do_register = fake_register_into_connection_manager

        data = (USR, PW)
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with successful response from server
        self.daemon._activation_check(self.socket, command, data)

        self.assertEqual(self.daemon.cfg['user'], USR)
        self.assertEqual(self.daemon.password, PW)
        self.assertFalse(old_activate_state, self.daemon.cfg['activate'])

        # Test the observing is not started
        self.assertFalse(self.init_observing_called)

    def test__activation_check_receive_registration_cmd_with_failed_registration_on_server(self):
        """
        Test that _activation_check receive registration cmd and registration failed on server.
        """
        def fake_register_into_connection_manager(data):
            return {'successful': False}

        #Mocking the communication with cmdmanager
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response

        command = 'register'
        self.daemon.conn_mng.do_register = fake_register_into_connection_manager

        data = (USR, PW)
        old_user = self.daemon.cfg['user']
        old_pass = self.daemon.password
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with failed response from server
        self.daemon._activation_check(self.socket, command, data)

        self.assertEqual(self.daemon.cfg['user'], old_user)
        self.assertEqual(self.daemon.password, old_pass)
        self.assertFalse(old_activate_state, self.daemon.cfg['activate'])

        # Test the observing is not started
        self.assertFalse(self.init_observing_called)

    def test__activation_check_receive_activation_cmd_with_success(self):
        """
        Test that _activation_check receive activation cmd and activation is successful.
        """
        def fake_activation_into_connection_manager(data):
            return {'successful': True}

        #Mocking the communication with cmdmanager
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response

        command = 'activate'
        self.daemon.conn_mng.do_activate = fake_activation_into_connection_manager

        data = (USR, 'token_authorized')
        old_user = self.daemon.cfg['user'] = USR
        old_pass = self.daemon.password = PW
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with successful response from server
        self.daemon._activation_check(self.socket, command, data)

        self.assertEqual(self.daemon.cfg['user'], USR, old_user)
        self.assertEqual(self.daemon.password, PW, old_pass)
        self.assertTrue(self.daemon.cfg['activate'])
        self.assertNotEqual(self.daemon.cfg['activate'], old_activate_state)

        # Test the observing is started
        self.assertTrue(self.init_observing_called)


    def test__activation_check_receive_activation_cmd_with_failed_activation_on_server(self):
        """
        Test that _activation_check receive activation cmd and activation failed on server.
        """
        def fake_activation_into_connection_manager(data):
            return {'successful': False}

        #Mocking the communication with cmdmanager
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response

        command = 'activate'
        self.daemon.conn_mng.do_activate = fake_activation_into_connection_manager

        data = (USR, 'unauthorized_token')
        old_user = self.daemon.cfg['user'] = USR
        old_pass = self.daemon.password = PW
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with failed response from server
        self.daemon._activation_check(self.socket, command, data)

        self.assertEqual(self.daemon.cfg['user'], old_user, USR)
        self.assertEqual(self.daemon.password, old_pass, PW)
        self.assertFalse(old_activate_state, self.daemon.cfg['activate'])

        # Test the observing is not started
        self.assertFalse(self.init_observing_called)

    def test__activation_check_receive_login_cmd_with_success(self):
        """
        Test that _activation_check receive login cmd with successful login.
        """

        def fake_login_into_connection_manager(data):
            return {'successful': True}

        #Mocking the communication with cmdmanager
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response

        command = 'login'
        self.daemon.conn_mng.do_login = fake_login_into_connection_manager

        data = (USR, PW)
        old_user = self.daemon.cfg['user']
        old_pass = self.daemon.password
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with successful response from server
        self.daemon._activation_check(self.socket, command, data)

        self.assertEquals(self.daemon.cfg['user'], USR, old_user)
        self.assertEquals(self.daemon.password, PW, old_pass)
        self.assertTrue(self.daemon.cfg['activate'])
        self.assertNotEqual(self.daemon.cfg['activate'], old_activate_state)

        # Test the observing is started
        self.assertTrue(self.init_observing_called)

    def test__activation_check_receive_login_cmd_with_failed_activation_on_server(self):
        """
        Test that _activation_check receive login cmd with failed activation on server.
        """

        def fake_login_into_connection_manager(data):
            return {'successful': False}

        #Mocking the communication with cmdmanager
        self.daemon._set_cmdmanager_response = fake_set_cmdmanager_response

        command = 'login'
        self.daemon.conn_mng.do_login = fake_login_into_connection_manager

        data = (USR, PW)
        old_user = self.daemon.cfg['user']
        old_pass = self.daemon.password
        old_activate_state = self.daemon.cfg['activate']

        # Call _activation_check with failed response from server
        self.daemon._activation_check(self.socket, command, data)

        self.assertEqual(self.daemon.cfg['user'], old_user)
        self.assertEqual(self.daemon.password, old_pass)
        self.assertFalse(self.daemon.cfg['activate'])
        self.assertEqual(self.daemon.cfg['activate'], old_activate_state)

        # Test the observing is started
        self.assertFalse(self.init_observing_called)


if __name__ == '__main__':
    unittest.main()
