#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import socket
import struct
import select
import os
import hashlib
import re
import time
import argparse
import keyring

from sys import exit as exit
from collections import OrderedDict
from shutil import copy2, move

# we import PollingObserver instead of Observer because the deleted event
# is not capturing https://github.com/gorakhargosh/watchdog/issues/46
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler
from connection_manager import ConnectionManager


class SkipObserver(Observer):
    def __init__(self, *args):
        Observer.__init__(self, *args)
        self._skip_list = []

    def skip(self, path):
        self._skip_list.append(path)
        print 'Path "{}" added to skip list!!!'.format(path)

    def dispatch_events(self, event_queue, timeout):
        event, watch = event_queue.get(block=True, timeout=timeout)
        skip = False
        try:
            event.dest_path
        except AttributeError:
            pass
        else:
            if event.dest_path in self._skip_list:
                self._skip_list.remove(event.dest_path)
                skip = True
        try:
            event.src_path
        except AttributeError as e:
            print e
        else:
            if event.src_path in self._skip_list:
                self._skip_list.remove(event.src_path)
                skip = True

        if not skip:
            self._dispatch_event(event, watch)

        event_queue.task_done()


def is_directory(method):
    def wrapper(self, e):
        if e.is_directory:
            return
        return method(self, e)
    return wrapper


class Daemon(FileSystemEventHandler):
    # The path for configuration directory and daemon configuration file
    CONFIG_DIR = os.path.join(os.environ['HOME'], '.PyBox')
    CONFIG_FILEPATH = os.path.join(CONFIG_DIR, 'daemon_config')

    # Default configuration for Daemon, loaded if fail to load the config file from CONFIG_DIR
    DEF_CONF = OrderedDict()
    DEF_CONF['local_dir_state_path'] = os.path.join(CONFIG_DIR, 'local_dir_state')
    DEF_CONF['sharing_path'] = os.path.join(os.environ['HOME'], 'sharing_folder')
    DEF_CONF['cmd_address'] = 'localhost'
    DEF_CONF['cmd_port'] = 50001
    DEF_CONF['api_suffix'] = '/API/V1/'
    DEF_CONF['server_address'] = 'http://localhost:5000'

    # Calculate int size in the machine architecture
    INT_SIZE = struct.calcsize('!i')

    # Allowed operation before user is activated
    ALLOWED_OPERATION = {'register', 'activate', 'login'}

    def __init__(self, cfg_path=None, sharing_path=None):
        FileSystemEventHandler.__init__(self)
        # Just Initialize variable the Daemon.start() do the other things
        self.daemon_state = 'down'  # TODO implement the daemon state (disconnected, connected, syncronizing, ready...)
        self.running = 0
        self.client_snapshot = {}  # EXAMPLE {'<filepath1>: ['<timestamp>', '<md5>', '<filepath2>: ...}
        self.shared_snapshot = {}
        self.local_dir_state = {}  # EXAMPLE {'last_timestamp': '<timestamp>', 'global_md5': '<md5>'}
        self.listener_socket = None
        self.observer = None
        self.cfg = self._load_cfg(cfg_path, sharing_path)
        self.password = self._load_pass()
        self._init_sharing_path(sharing_path)

        self.conn_mng = ConnectionManager(self.cfg)

        self.INTERNAL_COMMANDS = {
            'addshare': self._add_share,
            'removeshare': self._remove_share,
            'removeshareduser': self._remove_shared_user,
        }

    def _build_directory(self, path):
        """
        Create a given directory if not existent
        :param path: the path of dir i want to create
        :return: boolean that indicate if the directory is now created or not.
        """
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except OSError:
                print '\nImpossible to create directory at the following path:\n{}\n'.format(path)
                return False
            else:
                print 'Created folder:\n', path
        return True

    def _create_cfg(self, cfg_path, sharing_path):
        """
        Create the configuration file of client_daemon.
        If is given custom path for cfg (cfg_path) or observed directory (sharing_path) the config file
        will be updated with that configuration.
        If no cfg_path is given as default we save in default path stored in Daemon.CONFIG_FILEPATH.
        If no sharing_path is given as default we save in default path stored in Daemon.DEF_CONF['sharing_path'].
        :param cfg_path: Path of config
        :param sharing_path: Indicate the path of observed directory
        """

        building_cfg = Daemon.DEF_CONF
        building_cfg['sharing_path'] = sharing_path
        if cfg_path != Daemon.CONFIG_FILEPATH:
            Daemon.CONFIG_FILEPATH = cfg_path
            Daemon.CONFIG_DIR = os.path.dirname(cfg_path)
            building_cfg['local_dir_state_path'] = os.path.join(Daemon.CONFIG_DIR, 'local_dir_state')
        if self._build_directory(Daemon.CONFIG_DIR):
            with open(Daemon.CONFIG_FILEPATH, 'w') as daemon_config:
                json.dump(building_cfg, daemon_config, skipkeys=True, ensure_ascii=True, indent=4)
            return building_cfg
        else:
            self.stop(1, 'Impossible to create cfg file into {}'.format(Daemon.CONFIG_DIR))

    def update_cfg(self):
        """
        Update cfg with new state in self.cfg
        """
        with open(Daemon.CONFIG_FILEPATH, 'w') as daemon_config:
            json.dump(self.cfg, daemon_config, skipkeys=True, ensure_ascii=True, indent=4)

    def _load_cfg(self, cfg_path, sharing_path):
        """
        Load config, if impossible to find it or config file is corrupted restore it and load default configuration
        :param cfg_path: Path of config
        :param sharing_path: Indicate the path of observed directory
        :return: dictionary containing configuration
        """
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, 'r') as fo:
                    loaded_config = OrderedDict()
                    for k, v in json.load(fo).iteritems():
                        loaded_config[k] = v
            except ValueError:
                print '\nImpossible to read "{0}"!' \
                      '\nConfig file overwrited and loaded with default configuration!\n'.format(cfg_path)
            else:
                # Check that all the key in DEF_CONF are in loaded_config
                if not [True for k in Daemon.DEF_CONF if k not in loaded_config]:
                    # In the case is all gone right we can update the CONFIG costant and return loaded_config
                    Daemon.CONFIG_FILEPATH = cfg_path
                    Daemon.CONFIG_DIR = os.path.dirname(cfg_path)
                    return loaded_config
                print '\nWarning "{0}" corrupted!\nConfig file overwrited and loaded with default configuration!\n'\
                    .format(cfg_path)
        else:
            print '\nWarning "{0}" doesn\'t exist!' \
                  '\nNew config file created and loaded with default configuration!\n'.format(cfg_path)
        return self._create_cfg(cfg_path, sharing_path)

    def _save_pass(self, password):
        """
        Save password in keyring
        """
        keyring.set_password('PyBox', self.cfg['user'], password)

    def _load_pass(self):
        """
        Load from keyring the password
        :return: the account password
        """
        return keyring.get_password('PyBox', self.cfg.get('user', ''))

    def _init_sharing_path(self, sharing_path):
        """
        Check that the sharing folder exists otherwise create it.
        If is not given custom sharing_path we use default stored into self.cfg['sharing_path']
        If is impossible to create the directory exit error message is given.
        """

        if self._build_directory(sharing_path):
            self.cfg['sharing_path'] = sharing_path
            self.update_cfg()
        else:
            self.stop(1, '\nImpossible to create sharing folder in path:\n{}\n'
                         'Check sharing_path value contained in cfg file:\n{}\n'
                      .format(self.cfg['sharing_path'], Daemon.CONFIG_FILEPATH))

    def build_client_snapshot(self):
        """
        Build a snapshot of the sharing folder with the following structure

        self.client_snapshot
        {
            "<file_path>":('<timestamp>', '<md5>')
        }
        """
        self.client_snapshot = {}
        for dirpath, dirs, files in os.walk(self.cfg['sharing_path']):
            for filename in files:
                filepath = os.path.join(dirpath, filename)
                rel_filepath = self.relativize_path(filepath)

                if not self._is_shared_file(rel_filepath):
                    self.client_snapshot[rel_filepath] = ['', self.hash_file(filepath)]

    def build_shared_snapshot(self):
        """
        Build the snapshot of the shared files according this structure:
        {
            "shared/<user>/<file_path>":('<timestamp>', '<md5>')
        }
        """
        response = self.conn_mng.dispatch_request('get_server_snapshot', '')
        if response['successful']:
            try:
                self.shared_snapshot = response['content']['shared_files']
            except KeyError:
                self.shared_snapshot = {}
        else:
            self.stop(1, '\nReceived None snapshot. Server down?\n')

        # check the consistency of client snapshot retrieved by the server with the real files on clients
        file_md5 = None
        for filepath in self.shared_snapshot.keys():
            file_md5 = self.hash_file(self.absolutize_path(filepath))
            if not file_md5 or file_md5 != self.shared_snapshot[filepath][1]:
                # force the re-download at next synchronization
                self.shared_snapshot.pop(filepath)

        # NOTE: for future implementation:
        #
        # At startup it can't know if the owner of shared file has removed that share, so the files will remain into
        # shared folder as a zombie files, that means they will not update their status
        #
        # P.S. It can't delete them because some files could be not shared files, so it's safe don't force
        # the deletion of them

    def _is_directory_modified(self):
        """
        The function check if the shared folder has been modified.
        It recalculate the md5 from client_snapshot and compares it with the global md5 stored in local_dir_state
        :return: True or False
        """

        if self.md5_of_client_snapshot() != self.local_dir_state['global_md5']:
            return True
        else:
            return False

    def search_md5(self, searched_md5):
        """
        Receive as parameter the md5 of a file and return the first knowed path with the same md5
        """
        for path, tupla in self.client_snapshot.iteritems():
            if searched_md5 in tupla[1]:
                return path
        else:
            return None

    def _make_copy_on_client(self, src, dst):
        """
        Copy the file from src to dst if the dst already exists will be overwritten
        :param src: the relative path of source file to copy
        :param dst: the relative path of destination file to copy
        :return: True or False
        """

        abs_src = self.absolutize_path(src)
        if not os.path.isfile(abs_src):
            return False
        abs_dst = self.absolutize_path(dst)
        dst_dir = os.path.dirname(abs_dst)

        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)
        # Skip next operation to prevent watchdog to see this copy on client
        self.observer.skip(abs_dst)
        try:
            copy2(abs_src, abs_dst)
        except IOError:
            return False

        self.client_snapshot[dst] = self.client_snapshot[src]
        return True

    def _make_move_on_client(self, src, dst):
        """
        Move the file from src to dst. if the dst already exists will be overwritten
        :param src: the relative path of source file to move
        :param dst: the relative path of destination file to move
        :return: True or False
        """

        abs_src = self.absolutize_path(src)
        if not os.path.isfile(abs_src):
            return False
        abs_dst = self.absolutize_path(dst)
        dst_dir = os.path.dirname(abs_dst)

        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)
        # Skip next operation to prevent watchdog to see this move on client
        self.observer.skip(abs_dst)
        try:
            move(abs_src, abs_dst)
        except IOError:
            return False

        self.client_snapshot[dst] = self.client_snapshot[src]
        self.client_snapshot.pop(src)
        return True

    def _make_delete_on_client(self, filepath):
        """
        Delete the file in filepath. In case of error print information about it.
        :param filepath: the path of file i will delete
        """
        abs_path = self.absolutize_path(filepath)
        # Skip next operation to prevent watchdog to see this delete
        self.observer.skip(abs_path)
        try:
            os.remove(abs_path)
        except OSError as e:
            print 'WARNING impossible delete file during SYNC on path: {}\n' \
                  'Error occurred: {}'.format(abs_path, e)
        if self.client_snapshot.pop(filepath, 'ERROR') != 'ERROR':
            print 'Deleted file on server during SYNC.\nDeleted filepath: ', abs_path
        else:
            print 'WARNING inconsistency error during delete operation!' \
                  'Impossible to find the following file in stored data (client_snapshot):\n', abs_path

    def _sync_process(self, server_timestamp, server_dir_tree, shared_dir_tree={}):
        # Makes the synchronization logic and return a list of commands to launch
        # for server synchronization

        def _filter_tree_difference(client_dir_tree, server_dir_tree):
            # process local dir_tree and server dir_tree
            # and makes a diffs classification
            # return a dict representing that classification
            # E.g. { 'new_on_server'     : <[<filepath>, ...]>,  # files in server, but not in client
            # 'modified'          : <[<filepath>, ...]>,  # files in server and client, but different
            # 'new_on_client'     : <[<filepath>, ...]>,  # files not in server, but in client
            # }
            client_files = set(client_dir_tree.keys())
            server_files = set(server_dir_tree.keys())

            new_on_server = list(server_files.difference(client_files))
            new_on_client = list(client_files.difference(server_files))
            modified = []

            for filepath in server_files.intersection(client_files):
                # check files md5

                if server_dir_tree[filepath][1] != client_dir_tree[filepath][1]:
                    modified.append(filepath)

            return {'new_on_server': new_on_server, 'modified': modified, 'new_on_client': new_on_client}

        def _check_md5(dir_tree, md5):
            result = []
            for k, v in dir_tree.iteritems():
                if md5 == v[1]:
                    result.append(k)
            return result

        local_timestamp = self.local_dir_state['last_timestamp']
        tree_diff = _filter_tree_difference(self.client_snapshot, server_dir_tree)
        shared_tree_diff = _filter_tree_difference(self.shared_snapshot, shared_dir_tree)
        sync_commands = []

        if self._is_directory_modified():
            if local_timestamp == server_timestamp:
                print 'local_timestamp == server_timestamp and directory IS modified'
                # simple case: the client has the command
                # it sends all folder modifications to server

                # files in server but not in client: remove them from server
                for filepath in tree_diff['new_on_server']:
                    sync_commands.append(('delete', filepath))
                    # self.conn_mng.dispatch_request('delete', {'filepath': filepath})

                # files modified in client: send modified files to server
                for filepath in tree_diff['modified']:
                    sync_commands.append(('modify', filepath))

                # files in client but not in server: upload them to server
                for filepath in tree_diff['new_on_client']:
                    sync_commands.append(('upload', filepath))
                    # self.conn_mng.dispatch_request('upload', {'filepath': filepath})

            else:  # local_timestamp < server_timestamp
                print 'local_timestamp < server_timestamp and directory IS modified'
                assert local_timestamp <= server_timestamp, 'e\' successo qualcosa di brutto nella sync, ' \
                                                            'local_timestamp > di server_timestamp '
                # the server has the command
                for filepath in tree_diff['new_on_server']:
                    file_timestamp, md5 = server_dir_tree[filepath]
                    existed_filepaths_on_client = _check_md5(self.client_snapshot, md5)
                    # If i found at least one path in client_snapshot with the same md5 of filepath this mean in the
                    # past client_snapshot have stored one or more files with the same md5 but different paths.

                    if existed_filepaths_on_client:
                        # it's a copy or a move
                        for path in existed_filepaths_on_client:
                            if path in tree_diff['new_on_client']:
                                if self._make_move_on_client(path, filepath):
                                    tree_diff['new_on_client'].remove(path)
                                    break
                                else:
                                    self.stop(0, 'move failed on in SYNC: src_path: {}, dest_path: {}'.format(path,
                                                                                                              filepath))
                        # we haven't found files deleted on server so it's a copy
                        else:
                            if not self._make_copy_on_client(path, filepath):
                                self.stop(0,
                                          'copy failed on in SYNC: src_path: {}, dest_path: {}'.format(path, filepath))

                    # the daemon don't know filepath, i will search more updated timestamp
                    else:
                        if file_timestamp > local_timestamp:
                            # the files in server is more updated
                            sync_commands.append(('download', filepath))
                            # self.conn_mng.dispatch_request('download', {'filepath': filepath})
                        else:
                            # the client has deleted the file, so delete it on server
                            sync_commands.append(('delete', filepath))
                            # self.conn_mng.dispatch_request('delete', {'filepath': filepath})

                for filepath in tree_diff['modified']:
                    file_timestamp, md5 = server_dir_tree[filepath]

                    if file_timestamp < local_timestamp:
                        # the client has modified the file, so update it on server
                        sync_commands.append(('modify', filepath))
                        # self.conn_mng.dispatch_request('modify', {'filepath': filepath})
                    else:
                        # it's the worst case:
                        # we have a conflict with server,
                        # someone has modified files while daemon was down and someone else has modified
                        # the same file on server
                        conflicted_path = ''.join([filepath, '.conflicted'])
                        self._make_copy_on_client(filepath, conflicted_path)
                        sync_commands.append(('upload', conflicted_path))
                        # self.conn_mng.dispatch_request('upload', {'filepath': conflicted_path})

                for filepath in tree_diff['new_on_client']:
                    sync_commands.append(('upload', filepath))
                    # self.conn_mng.dispatch_request('upload', {'filepath': filepath})

        else:  # directory not modified
            if local_timestamp == server_timestamp:
                print 'local_timestamp == server_timestamp and directory IS NOT modified'
                # it's the best case. Client and server are already synchronized
                for key in tree_diff:
                    assert not tree_diff[key], "local_timestamp == server_timestamp but tree_diff is not empty!\ntree_diff:\n{}".format(tree_diff)
                sync_commands = []
            else:  # local_timestamp < server_timestamp
                print 'local_timestamp < server_timestamp and directory IS NOT modified'
                assert local_timestamp <= server_timestamp, 'ERROR something bad happen during SYNC process, ' \
                                                            'local_timestamp > di server_timestamp'
                # the server has the command
                for filepath in tree_diff['new_on_server']:
                    timestamp, md5 = server_dir_tree[filepath]
                    existed_filepaths_on_client = _check_md5(self.client_snapshot, md5)
                    # If i found at least one path in client_snapshot with the same md5 of filepath this mean that
                    # in the past client_snapshot have stored one or more files with the same md5 but different paths.

                    if existed_filepaths_on_client:
                        # it's a copy or a move
                        for path in existed_filepaths_on_client:
                            if path in tree_diff['new_on_client']:
                                if self._make_move_on_client(path, filepath):
                                    tree_diff['new_on_client'].remove(path)
                                    break
                                else:
                                    self.stop(0, 'move failed on in SYNC: src_path: {}, dest_path: {}'.format(path,
                                                                                                              filepath))
                        # we haven't found files deleted on server so it's a copy
                        else:
                            if not self._make_copy_on_client(path, filepath):
                                self.stop(0,
                                          'copy failed on in SYNC: src_path: {}, dest_path: {}'.format(path, filepath))
                    else:
                        # it's a new file
                        sync_commands.append(('download', filepath))
                        # self.conn_mng.dispatch_request('download', {'filepath': filepath})

                for filepath in tree_diff['modified']:
                    self._make_delete_on_client(filepath)
                    sync_commands.append(('download', filepath))
                    # self.conn_mng.dispatch_request('download', {'filepath': filepath})

                for filepath in tree_diff['new_on_client']:
                    # files that have been deleted on server, so we have to delete them
                    self._make_delete_on_client(filepath)

        for filepath in shared_tree_diff['new_on_client']:
            # files deleted on server
            abs_filepath = self.absolutize_path(filepath)
            self.observer.skip(abs_filepath)
            try:
                os.remove(abs_filepath)
            except OSError as ex:
                print "Delete EXEPTION INTO SYNC : {}".format(ex)

            self.shared_snapshot.pop(filepath)

        for filepath in shared_tree_diff['modified']:
            sync_commands.append(('download', filepath))

        for filepath in shared_tree_diff['new_on_server']:
            sync_commands.append(('download', filepath))

        return sync_commands

    def sync_with_server(self):
        """
        Makes the synchronization with server
        """
        response = self.conn_mng.dispatch_request('get_server_snapshot', '')
        if not response['successful']:
            self.stop(1, response['content'])

        server_timestamp = response['content']['server_timestamp']
        server_snapshot = response['content']['files']

        try:
            shared_files = response['content']['shared_files']
        except KeyError:
            shared_files = {}

        sync_commands = self._sync_process(server_timestamp, server_snapshot, shared_files)

        # Initialize the variable where we put the timestamp of the last operation we did
        last_operation_timestamp = server_timestamp

        # makes all synchronization commands
        for command, path in sync_commands:
            if command == 'delete':
                abs_path = self.absolutize_path(path)
                response = self.conn_mng.dispatch_request(command, {'filepath': path})
                if response['successful']:
                    last_operation_timestamp = response['content']['server_timestamp']
                    if self.client_snapshot.pop(path, 'ERROR') != 'ERROR':
                        print 'Deleted file on server during SYNC.\nDeleted filepath: ', abs_path
                    else:
                        print 'WARNING inconsistency error during delete operation!' \
                              'Impossible to find the following file in stored data (client_snapshot):\n', abs_path
                else:
                    self.stop(1, response['content'])

            elif command == 'modify' or command == 'upload':
                abs_path = self.absolutize_path(path)
                new_md5 = self.hash_file(abs_path)
                response = self.conn_mng.dispatch_request(command, {'filepath': path, 'md5': new_md5})
                if response['successful']:
                    last_operation_timestamp = response['content']['server_timestamp']
                    print '{} file on server during SYNC.\n{} filepath: {}'\
                        .format(('Modified', 'Updated')[command == 'modify'], abs_path)
                else:
                    self.stop(1, response['content'])

            else:  # command == 'download'
                abs_path = self.absolutize_path(path)
                # Skip next operation to prevent watchdog to see this download
                self.observer.skip(abs_path)
                response = self.conn_mng.dispatch_request(command, {'filepath': path})
                if response['successful']:
                    if self._is_shared_file(path):
                        self.shared_snapshot[path] = shared_files[path]
                    else:
                        print 'Downloaded file from server during SYNC.\nDownloaded filepath: {}'.format(abs_path)
                        self.client_snapshot[path] = server_snapshot[path]
                else:
                    self.stop(1, response['content'])

        self.update_local_dir_state(last_operation_timestamp)

    def _is_shared_file(self, path):
        """
        Check if the given path is a shared file.(Check if is located in 'shared' folder)
        :param path:
        :return: True, False
        """

        if path.split('/')[0] == 'shared':
            return True
        return False

    def relativize_path(self, abs_path):
        """
        This function relativize the path watched by daemon:
        for example: /home/user/watched/subfolder/ will be subfolder/
        """
        if abs_path.startswith(self.cfg['sharing_path']):
            relative_path = abs_path[len(self.cfg['sharing_path']) + 1:]
            return relative_path
        else:
            raise Exception

    def absolutize_path(self, rel_path):
        """
        This function absolutize a path that i have relativize before:
        for example: subfolder/ will be /home/user/watched/subfolder/
        """
        return os.path.join(self.cfg['sharing_path'], rel_path)

    @is_directory
    def on_created(self, e):
        """
        Manage the create event observed from watchdog.
        The data about the event is collected and sent to the server with connection_manager module.
        After the result of connection is received with successful response the client_snapshot and local_dir_state
        will be updated.

        N.B: Sometime on_created event is a copy or modify event for erroneous survey,
        so the method check if this error has happened.
        :param e: event object with information about what has happened
        """
        def build_data(cmd, rel_new_path, new_md5, founded_path=None):
            """
            Prepares the data from event handler to be delivered to connection_manager.
            """
            data = {'cmd': cmd}
            if cmd == 'copy':
                data['file'] = {'src': founded_path,
                                'dst': rel_new_path,
                                'md5': new_md5}
            else:
                data['file'] = {'filepath': rel_new_path,
                                'md5': new_md5}
            return data

        new_md5 = self.hash_file(e.src_path)
        rel_new_path = self.relativize_path(e.src_path)
        founded_path = self.search_md5(new_md5)
        # with this check i found the copy events
        if founded_path:
            abs_founded_path = self.absolutize_path(founded_path)
            print 'Start copy from path : {}\n to path: {}'.format(abs_founded_path, e.src_path)
            data = build_data('copy', rel_new_path, new_md5, founded_path)
        # this elif check that this create event aren't modify event.
        # Normally this never happen but sometimes watchdog fail to understand what has happened on file.
        # For example Gedit generate a create event instead modify event when a file is saved.
        elif rel_new_path in self.client_snapshot:
            print 'WARNING this is modify event FROM CREATE EVENT! Path of file already existent:', e.src_path
            data = build_data('modify', rel_new_path, new_md5)

        else:  # Finally we find a real create event!
            print 'Start create in path:', e.src_path
            data = build_data('upload', rel_new_path, new_md5)

        # Send data to connection manager dispatcher and check return value.
        # If all go right update client_snapshot and local_dir_state
        if self._is_shared_file(rel_new_path):
            print 'you are writing file into a read-only folder, so it will not be synchronized with server'
        else:
            response = self.conn_mng.dispatch_request(data['cmd'], data['file'])
            if response['successful']:
                event_timestamp = response['content']['server_timestamp']
                self.client_snapshot[rel_new_path] = [event_timestamp, new_md5]
                self.update_local_dir_state(event_timestamp)
                print '{} event completed.'.format(data['cmd'])
            else:
                self.stop(1, response['content'])

    @is_directory
    def on_moved(self, e):
        """
        Manage the move event observed from watchdog.
        The data about the event is collected and sent to the server with connection_manager module.
        After the result of connection is received with successful response the client_snapshot and local_dir_state
        will be updated.

        N.B: Sometime on_move event is a copy event for erroneous survey, so the method check if this error has happened.
        :param e: event object with information about what has happened
        """

        print 'Start move from path : {}\n to path: {}'.format(e.src_path,e.dest_path)

        rel_src_path = self.relativize_path(e.src_path)
        rel_dest_path = self.relativize_path(e.dest_path)

        source_shared = self._is_shared_file(rel_src_path)
        dest_shared = self._is_shared_file(rel_dest_path)

        # this check that move event isn't modify event.
        # Normally this never happen but sometimes watchdog fail to understand what has happened on file.
        # For example Gedit generate a move event instead copy event when a file is saved.
        if not os.path.exists(e.src_path):
            cmd = 'move'
        else:
            print 'WARNING this is COPY event from MOVE EVENT!'
            cmd = 'copy'

        if source_shared and not dest_shared:  # file moved from shared path to not shared path
            # upload the file
            new_md5 = self.hash_file(e.dest_path)
            data = {
                'filepath': rel_dest_path,
                'md5': new_md5
            }

            response = self.conn_mng.dispatch_request('upload', data)
            if response['successful']:
                event_timestamp = response['content']['server_timestamp']
                self.client_snapshot[rel_dest_path] = [event_timestamp, new_md5]
                self.update_local_dir_state(event_timestamp)

                if cmd == 'move':
                    # force the re-download of the file at next synchronization
                    try:
                        self.shared_snapshot.pop(rel_src_path)
                    except KeyError:
                        pass
            else:
                self.stop(1, response['content'])

        elif source_shared and dest_shared:  # file moved from shared path to shared path
            if cmd == 'move':
                # force the re-download of the file moved at the next synchronization
                try:
                    self.shared_snapshot.pop(rel_src_path)
                except KeyError:
                    pass

            # if it has modified a file tracked by shared snapshot, then force the re-download of it
            try:
                self.shared_snapshot.pop(rel_dest_path)
            except KeyError:
                pass

        elif not source_shared and dest_shared:  # file moved from not shared path to shared path
            if cmd == 'move':
                # delete file on server
                response = self.conn_mng.dispatch_request('delete', {'filepath': rel_src_path})
                if response['successful']:
                    event_timestamp = response['content']['server_timestamp']
                    if self.client_snapshot.pop(rel_src_path, 'ERROR') == 'ERROR':
                        print 'Error during delete event! Impossible to find "{}" inside client_snapshot'.format(
                            rel_src_path)
                    self.update_local_dir_state(event_timestamp)
                else:
                    self.stop(1, response['content'])

            # if it has modified a file tracked by shared snapshot, then force the re-download of it
            try:
                self.shared_snapshot.pop(rel_dest_path)
            except KeyError:
                pass

        else:  # file moved from not shared path to not shared path (standard case)
            if not self.client_snapshot.get(rel_src_path)[1]:
                self.stop(1, 'WARNING inconsistency error during {} operation!\n'
                             'Impossible to find the following file in stored data (client_snapshot):\n{}'.format(cmd, rel_src_path))
            md5 = self.client_snapshot[rel_src_path][1]
            data = {'src': rel_src_path,
                    'dst': rel_dest_path,
                    'md5': md5}
            # Send data to connection manager dispatcher and check return value.
            # If all go right update client_snapshot and local_dir_state
            response = self.conn_mng.dispatch_request(cmd, data)
            if response['successful']:
                event_timestamp = response['content']['server_timestamp']
                self.client_snapshot[rel_dest_path] = [event_timestamp, md5]
                if cmd == 'move':
                    # rel_src_path already checked
                    self.client_snapshot.pop(rel_src_path)
                self.update_local_dir_state(event_timestamp)
                print '{} event completed.'.format(cmd)
            else:
                self.stop(1, response['content'])

    @is_directory
    def on_modified(self, e):
        """
        Manage the modify event observed from watchdog.
        The data about the event is collected and sent to the server with connection_manager module.
        After the result of connection is received with successful response the client_snapshot and local_dir_state
        will be updated.
        :param e: event object with information about what has happened
        """
        print 'start modify of file:', e.src_path
        new_md5 = self.hash_file(e.src_path)
        rel_path = self.relativize_path(e.src_path)
        data = {'filepath': rel_path,
                'md5': new_md5
                }

        if self._is_shared_file(rel_path):
            # if it has modified a file tracked by shared snapshot, then force the re-download of it
            try:
                self.shared_snapshot.pop(rel_path)
            except KeyError:
                pass
        else:
            # Send data to connection manager dispatcher and check return value.
            # If all go right update client_snapshot and local_dir_state
            response = self.conn_mng.dispatch_request('modify', data)
            if response['successful']:
                event_timestamp = response['content']['server_timestamp']
                self.client_snapshot[rel_path] = [event_timestamp, new_md5]
                self.update_local_dir_state(event_timestamp)
                print 'Modify event completed.'
            else:
                self.stop(1, response['content'])

    @is_directory
    def on_deleted(self, e):
        """
        Manage the delete event observed from watchdog.
        The data about the event is collected and sent to the server with connection_manager module.
        After the result of connection is received with successful response the client_snapshot and local_dir_state
        will be updated.
        :param e: event object with information about what has happened
        """
        print 'start delete of file:', e.src_path
        rel_path = self.relativize_path(e.src_path)

        if self._is_shared_file(rel_path):
            # if it has modified a file tracked by shared snapshot, then force the re-download of it
            try:
                self.shared_snapshot.pop(rel_path)
            except KeyError:
                pass
        else:
            # Send data to connection manager dispatcher and check return value.
            # If all go right update client_snapshot and local_dir_state
            response = self.conn_mng.dispatch_request('delete', {'filepath': rel_path})
            if response['successful']:
                event_timestamp = response['content']['server_timestamp']
                if self.client_snapshot.pop(rel_path, 'ERROR') == 'ERROR':
                    print 'WARNING inconsistency error during delete operation!' \
                          'Impossible to find the following file in stored data (client_snapshot):\n', e.src_path
                self.update_local_dir_state(event_timestamp)
                print 'Delete event completed.'
            else:
                self.stop(1, response['content'])

    def _get_cmdmanager_request(self, socket):
        """
        Communicate with cmd_manager and get the request
        Returns the request decoded by json format or None if cmd_manager send connection closure
        """
        packet_size = socket.recv(Daemon.INT_SIZE)
        if len(packet_size) == Daemon.INT_SIZE:

            packet_size = int(struct.unpack('!i', packet_size)[0])
            packet = ''
            remaining_size = packet_size

            while len(packet) < packet_size:
                packet_buffer = socket.recv(remaining_size)
                remaining_size -= len(packet_buffer)
                packet = ''.join([packet, packet_buffer])

            req = json.loads(packet)
            return req
        else:
            return None

    def _set_cmdmanager_response(self, socket, message):
        """
        Makes cmd_manager response encoding it in json format and send it to cmd_manager
        """
        response = {'message': message}
        response_packet = json.dumps(response)
        socket.sendall(struct.pack('!i', len(response_packet)))
        socket.sendall(response_packet)
        return response_packet

    def _initialize_observing(self):
        """
        Intial operation for observing.
        We create the client_snapshot, load the information stored inside local_dir_state and create observer.
        """
        self.build_client_snapshot()
        self.build_shared_snapshot()
        self.load_local_dir_state()
        self.create_observer()
        self.observer.start()
        self.sync_with_server()

    def create_observer(self):
        """
        Create an instance of the watchdog Observer thread class.
        """
        self.observer = SkipObserver()
        self.observer.schedule(self, path=self.cfg['sharing_path'], recursive=True)

    def _activation_check(self, s, cmd, data):
        """
        This method allow only registration and activation of user until this will be accomplished.
        In case of bad cmd this will be refused otherwise if the server response are successful
        we update the daemon_config and after activation of user start the observing.
        In case of login we do registration and activation together
        :param s: connection socket with client_cmdmanager
        :param cmd: received cmd from client_cmdmanager
        :param data: received data from client_cmdmanager
        """
        def store_registration_data():
            """
            update cfg with userdata
            """
            self.cfg['user'] = data[0]
            self.update_cfg()
            self.password = data[1]
            self._save_pass(data[1])

        def activate_daemon():
            """
            activate observing and update cfg['activate'] state at True in all loaded cfg
            """
            self.cfg['activate'] = True
            # Update the information about cfg into connection manager and cfg file
            self.conn_mng.load_cfg(self.cfg)
            self.update_cfg()
            # Now the client_daemon is ready to operate, we do the start activity
            self._initialize_observing()

        if cmd not in Daemon.ALLOWED_OPERATION:
            response = {'content': 'Operation not allowed! Authorization required.',
                        'successful': False}
        else:
            response = self.conn_mng.dispatch_request(cmd, data)
            if response['successful']:
                if cmd == 'register':
                    store_registration_data()
                elif cmd == 'activate':
                    activate_daemon()
                elif cmd == 'login':
                    store_registration_data()
                    activate_daemon()
        return response

    def start(self):
        """
        Starts the communication with the command_manager.
        """
        # If user is activated we can start observing.
        if self.cfg.get('activate'):
            self._initialize_observing()

        TIMEOUT_LISTENER_SOCK = 0.5
        BACKLOG_LISTENER_SOCK = 1
        self.listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener_socket.bind((self.cfg['cmd_address'], self.cfg['cmd_port']))
        self.listener_socket.listen(BACKLOG_LISTENER_SOCK)
        r_list = [self.listener_socket]
        self.daemon_state = 'started'
        self.running = 1
        polling_counter = 0
        try:
            while self.running:
                r_ready, w_ready, e_ready = select.select(r_list, [], [], TIMEOUT_LISTENER_SOCK)

                for s in r_ready:

                    if s == self.listener_socket:
                        # handle the server socket
                        client_socket, client_address = self.listener_socket.accept()
                        r_list.append(client_socket)
                    else:
                        # handle all other sockets
                        req = self._get_cmdmanager_request(s)

                        if req:
                            for cmd, data in req.items():
                                # TODO is required to refact/reingeneering stop/shutdown for a clean closure
                                # now used an expedient (raise KeyboardInterrupt) to make it runnable
                                if cmd == 'shutdown':
                                    response = {'content': 'Daemon is shutting down', 'successful': True}
                                    self._set_cmdmanager_response(s, response)
                                    raise KeyboardInterrupt

                                if not self.cfg.get('activate'):
                                    response = self._activation_check(s, cmd, data)
                                elif cmd == 'login':
                                    response = {'content': 'Warning! There is a user already authenticated on this '
                                                           'computer. Impossible to login account',
                                                'successful': False}

                                else:  # client is already activated
                                    try:
                                        response = self.INTERNAL_COMMANDS[cmd](data)
                                    except KeyError:
                                        response = self.conn_mng.dispatch_request(cmd, data)
                                        # for now the protocol is that for request sent by
                                        # command manager, the server reply with a string
                                        # so, to maintain the same data structure during
                                        # daemon and cmdmanager comunications, it rebuild a json
                                        # to send like response
                                        # TODO it's advisable to make attention to this assertion or refact the architecture

                                self._set_cmdmanager_response(s, response)
                        else:  # it receives the FIN packet that close the connection
                            s.close()
                            r_list.remove(s)

                if self.cfg.get('activate'):
                    # synchronization polling
                    # makes the polling every 3 seconds, so it waits six cycle (0.5 * 6 = 3 seconds)
                    # maybe optimizable but now functional
                    polling_counter += 1
                    if polling_counter == 6:
                        polling_counter = 0
                        self.sync_with_server()

        except KeyboardInterrupt:
            self.stop(0)
        if self.cfg.get('activate'):
            self.observer.stop()
            self.observer.join()
        self.listener_socket.close()

    def _validate_path(self, path):

        if os.path.exists(''.join([self.cfg['sharing_path'], os.sep, path])):
            return True
        return False

    def _add_share(self, data):
        """
        handle the adding of shared folder with a user
        """
        shared_folder = data[0]
        if not self._validate_path(shared_folder):
            return '\'%s\' not exists' % shared_folder

        return self.conn_mng.dispatch_request('addshare', data)

    def _remove_share(self, data):
        """
        handle the removing of a shared folder
        """
        shared_folder = data[0]
        if not self._validate_path(shared_folder):
            return '\'%s\' not exists' % shared_folder

        return self.conn_mng.dispatch_request('removeshare', data)

    def _remove_shared_user(self, data):
        """
        handle the removing of an user from a shared folder
        """
        shared_folder = data[0]
        if not self._validate_path(shared_folder):
            return '\'%s\' not exists' % shared_folder

        return self.conn_mng.dispatch_request('removeshareduser', data)

    def stop(self, exit_status, exit_message=None):
        """
        Stop the Daemon components (observer and communication with command_manager).
        """
        if self.daemon_state == 'started':
            self.running = 0
            self.daemon_state = 'down'
            if self.local_dir_state:
                self.save_local_dir_state()
        if exit_message:
            print exit_message
        exit(exit_status)

    def update_local_dir_state(self, last_timestamp):
        """
        Update the local_dir_state with last_timestamp operation and save it on disk
        """

        self.local_dir_state['last_timestamp'] = last_timestamp
        self.local_dir_state['global_md5'] = self.md5_of_client_snapshot()
        self.save_local_dir_state()

    def save_local_dir_state(self):
        """
        Save local_dir_state on disk
        """
        json.dump(self.local_dir_state, open(self.cfg['local_dir_state_path'], 'w'), indent=4)
        print 'local_dir_state saved'

    def load_local_dir_state(self):
        """
        Load local dir state on self.local_dir_state variable
        if file doesn't exists it will be created without timestamp
        """

        def _rebuild_local_dir_state():
            self.local_dir_state = {'last_timestamp': 0, 'global_md5': self.md5_of_client_snapshot()}
            json.dump(self.local_dir_state, open(self.cfg['local_dir_state_path'], 'w'), indent=4)

        if os.path.isfile(self.cfg['local_dir_state_path']):
            self.local_dir_state = json.load(open(self.cfg['local_dir_state_path'], 'r'))
            print 'Loaded local_dir_state'
        else:
            print 'local_dir_state not found. Initialize new local_dir_state'
            _rebuild_local_dir_state()

    def md5_of_client_snapshot(self, verbose=0):
        """
        Calculate the md5 of the entire directory snapshot,
        with the md5 in client_snapshot and the md5 of full filepath string.
        :return is the md5 hash of the directory
        """

        if verbose:
            start = time.time()
        md5hash = hashlib.md5()

        for path, time_md5 in sorted(self.client_snapshot.iteritems()):
            # extract md5 from tuple. we don't need hexdigest it's already md5
            if verbose:
                print path
            md5hash.update(time_md5[1])
            md5hash.update(path)

        if verbose:
            stop = time.time()
            print stop - start
        return md5hash.hexdigest()

    def hash_file(self, file_path, chunk_size=1024):
        """
        :accept an absolute file path
        :return the md5 hash of received file
        """

        md5hash = hashlib.md5()
        try:
            f1 = open(file_path, 'rb')
            while 1:
                # Read file in as little chunks
                buf = f1.read(chunk_size)
                if not buf:
                    break
                md5hash.update(buf)
            f1.close()
            return md5hash.hexdigest()
        except (OSError, IOError) as e:
            print e
            return None


def is_valid_file(string):
    if os.path.isfile(string) or string == DEF_CFG_FILEPATH:
        return string
    else:
        parser.error('The path "%s" does not be a valid file!' % string)


def is_valid_dir(string):
    if os.path.isdir(string) or string == DEF_SHARING_PATH:
        return string
    else:
        parser.error('The path "%s" does not be a valid directory!' % string)

if __name__ == '__main__':
    DEF_SHARING_PATH = Daemon.DEF_CONF['sharing_path']
    DEF_CFG_FILEPATH = Daemon.CONFIG_FILEPATH
    parser = argparse.ArgumentParser()
    parser.add_argument('-cfg', help='the configuration file filepath', type=is_valid_file, default=DEF_CFG_FILEPATH)
    parser.add_argument('-sh', help='the sharing path that we will observing', type=is_valid_dir,
                        default=DEF_SHARING_PATH, dest='custom_sharing_path')

    args = parser.parse_args()
    daemon = Daemon(args.cfg, args.custom_sharing_path)
    daemon.start()
