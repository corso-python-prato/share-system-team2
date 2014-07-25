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

from sys import exit as exit
from collections import OrderedDict
from shutil import copy2, move

# we import PollingObserver instead of Observer because the deleted event
# is not capturing https://github.com/gorakhargosh/watchdog/issues/46
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import RegexMatchingEventHandler
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


class Daemon(RegexMatchingEventHandler):
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
    DEF_CONF['user'] = 'pasquale'
    DEF_CONF['pass'] = 'secretpass'
    DEF_CONF['timeout_listener_sock'] = 0.5
    DEF_CONF['backlog_listener_sock'] = 1

    IGNORED_REGEX = ['.*\.[a-zA-z]+?#',  # Libreoffice suite temporary file ignored
                     '.*\.[a-zA-Z]+?~',  # gedit issue solved ignoring this pattern:
                     # gedit first delete file, create, and move to dest_path *.txt~
                    ]

    # Calculate int size in the machine architecture
    INT_SIZE = struct.calcsize('!i')

    def __init__(self, cfg_path=None):
        RegexMatchingEventHandler.__init__(self, ignore_regexes=Daemon.IGNORED_REGEX, ignore_directories=True)

        # Just Initialize variable the Daemon.start() do the other things
        self.daemon_state = 'down'  # TODO implement the daemon state (disconnected, connected, syncronizing, ready...)
        self.running = 0
        self.client_snapshot = {}  # EXAMPLE {'<filepath1>: ['<timestamp>', '<md5>', '<filepath2>: ...}
        self.local_dir_state = {}  # EXAMPLE {'last_timestamp': '<timestamp>', 'global_md5': '<md5>'}
        self.listener_socket = None
        self.observer = None

        if cfg_path:
            self.cfg = self.load_cfg(cfg_path)
        else:
            self.cfg = self.load_cfg(Daemon.CONFIG_FILEPATH)

        self.init_sharing_path()
        self.conn_mng = ConnectionManager(self.cfg)

    def load_cfg(self, config_path):
        """
        Load config, if impossible to find it or config file is corrupted restore it and load default configuration
        :param config_path: Path of config
        :return: dictionary containing configuration
        """

        def build_default_cfg():
            """
            Restore default config file by writing on file
            :return: default configuration contained in the dictionary DEF_CONF
            """
            with open(Daemon.CONFIG_FILEPATH, 'wb') as fo:
                json.dump(Daemon.DEF_CONF, fo, skipkeys=True, ensure_ascii=True, indent=4)
            return Daemon.DEF_CONF

        # Search if config directory exists otherwise create it
        if not os.path.isdir(Daemon.CONFIG_DIR):
            try:
                os.makedirs(Daemon.CONFIG_DIR)
            except (OSError, IOError):
                self.stop(1, '\nImpossible to create "{}" directory! Permission denied!\n'.format(Daemon.CONFIG_DIR))

        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r') as fo:
                    loaded_config = json.load(fo)
            except ValueError:
                print '\nImpossible to read "{0}"! Config file overwrited and loaded default config!\n'.format(
                    config_path)
                return build_default_cfg()
            corrupted_config = False
            for k in Daemon.DEF_CONF:
                if k not in loaded_config:
                    corrupted_config = True
            # In the case is all gone right run config in loaded_config
            if not corrupted_config:
                return loaded_config
            else:
                print '\nWarning "{0}" corrupted! Config file overwrited and loaded default config!\n'.format(
                    config_path)
                return build_default_cfg()
        else:
            print '\nWarning "{0}" doesn\'t exist, Config file overwrited and loaded default config!\n'.format(
                config_path)
            return build_default_cfg()

    def init_sharing_path(self):
        """
        Check that the sharing folder exists otherwise create it.
        If is impossible to create exit with msg error.
        """
        if not os.path.isdir(self.cfg['sharing_path']):
            try:
                os.makedirs(self.cfg['sharing_path'])
            except OSError:
                self.stop(1,
                          '\nImpossible to create "{0}" directory! Check sharing_path value contained in the following file:\n"{1}"\n'
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
                unwanted_file = False
                for r in Daemon.IGNORED_REGEX:
                    if re.match(r, filepath) is not None:
                        unwanted_file = True
                        print 'Ignored Path:', filepath
                        break
                if not unwanted_file:
                    relative_path = self.relativize_path(filepath)
                    self.client_snapshot[relative_path] = ['', self.hash_file(filepath)]

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

    def _make_copy_on_client(self, src, dst, server_timestamp):
        """
        Copy the file from src to dst if the dst already exists will be overwritten
        :param src: the relative path of source file to copy
        :param dst: the relative path of destination file to copy
        :return: True or False
        """

        abs_src = self.absolutize_path(src)
        if not os.path.isfile(abs_src): return False

        abs_dst = self.absolutize_path(dst)
        dst_dir = os.path.dirname(abs_dst)

        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)

        self.observer.skip(abs_dst)
        try:
            copy2(abs_src, abs_dst)
        except IOError as e:
            return False

        self.client_snapshot[dst] = self.client_snapshot[src]
        self.update_local_dir_state(server_timestamp)
        return True

    def _make_move_on_client(self, src, dst, server_timestamp):
        """
        Move the file from src to dst. if the dst already exists will be overwritten
        :param src: the relative path of source file to move
        :param dst: the relative path of destination file to move
        :return: True or False
        """

        abs_src = self.absolutize_path(src)
        if not os.path.isfile(abs_src): return False

        abs_dst = self.absolutize_path(dst)
        dst_dir = os.path.dirname(abs_dst)

        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)

        self.observer.skip(abs_dst)
        try:
            move(abs_src, abs_dst)
        except IOError as e:
            return False

        self.client_snapshot[dst] = self.client_snapshot[src]
        self.client_snapshot.pop(src)
        self.update_local_dir_state(server_timestamp)
        return True

    def _sync_process(self, server_timestamp, server_dir_tree):
        # Makes the synchronization logic and return a list of commands to launch
        # for server synchronization

        def _filter_tree_difference(server_dir_tree):
            # process local dir_tree and server dir_tree
            # and makes a diffs classification
            # return a dict representing that classification
            # E.g. { 'new_on_server'     : <[<filepath>, ...]>,  # files in server, but not in client
            # 'modified'          : <[<filepath>, ...]>,  # files in server and client, but different
            # 'new_on_client'     : <[<filepath>, ...]>,  # files not in server, but in client
            # }
            client_files = set(self.client_snapshot.keys())
            server_files = set(server_dir_tree.keys())

            new_on_server = list(server_files.difference(client_files))
            new_on_client = list(client_files.difference(server_files))
            modified = []

            for filepath in server_files.intersection(client_files):
                # check files md5

                if server_dir_tree[filepath][1] != self.client_snapshot[filepath][1]:
                    modified.append(filepath)

            return {'new_on_server': new_on_server, 'modified': modified, 'new_on_client': new_on_client}



        def _check_md5(dir_tree, md5):
            result = []
            for k, v in dir_tree.items():
                if md5 == v[1]:
                    result.append(k)
            return result

        local_timestamp = self.local_dir_state['last_timestamp']
        tree_diff = _filter_tree_difference(server_dir_tree)
        sync_commands = []

        if self._is_directory_modified():
            if local_timestamp == server_timestamp:
                print "local_timestamp == server_timestamp and directory IS modified"
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
                print "local_timestamp < server_timestamp and directory IS modified"
                assert local_timestamp <= server_timestamp, 'e\' successo qualcosa di brutto nella sync, ' \
                                                            'local_timestamp > di server_timestamp '
                # the server has the command
                for filepath in tree_diff['new_on_server']:
                    file_timestamp, md5 = server_dir_tree[filepath]
                    existed_filepaths_on_client = _check_md5(self.client_snapshot, md5)
                    # If i found at least one path in client_snapshot with the same md5 of filepath this mean that in the past
                    # client_snapshot have stored one or more files with the same md5 but different paths.

                    if existed_filepaths_on_client:
                        # it's a copy or a move
                        for path in existed_filepaths_on_client:
                            if path in tree_diff['new_on_client']:
                                if self._make_move_on_client(path, filepath, server_timestamp):
                                    tree_diff['new_on_client'].remove(path)
                                    break
                                else:
                                    self.stop(0, "move failed on in SYNC: src_path: {}, dest_path: {}".format(path, filepath))
                        # we haven't found files deleted on server so it's a copy
                        else:
                            if not self._make_copy_on_client(path, filepath, server_timestamp):
                                self.stop(0, "copy failed on in SYNC: src_path: {}, dest_path: {}".format(path, filepath))

                    # the daemon don't know filepath, i will search if the file_timestamp is more recent then local_timestamp
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
                        self._make_copy_on_client(filepath, conflicted_path, server_timestamp)
                        sync_commands.append(('upload', conflicted_path))
                        # self.conn_mng.dispatch_request('upload', {'filepath': conflicted_path})

                for filepath in tree_diff['new_on_client']:
                    sync_commands.append(('upload', filepath))
                    # self.conn_mng.dispatch_request('upload', {'filepath': filepath})

        else:  # directory not modified
            if local_timestamp == server_timestamp:
                print "local_timestamp == server_timestamp and directory IS NOT modified"
                # it's the best case. Client and server are already synchronized
                return []
            else:  # local_timestamp < server_timestamp
                print "local_timestamp < server_timestamp and directory IS NOT modified"
                assert local_timestamp <= server_timestamp, 'e\' successo qualcosa di brutto nella sync, ' \
                                                            'local_timestamp > di server_timestamp '
                # the server has the command
                for filepath in tree_diff['new_on_server']:
                    timestamp, md5 = server_dir_tree[filepath]
                    existed_filepaths_on_client = _check_md5(self.client_snapshot, md5)
                    # If i found at least one path in client_snapshot with the same md5 of filepath this mean that in the past
                    # client_snapshot have stored one or more files with the same md5 but different paths.

                    if existed_filepaths_on_client:
                        # it's a copy or a move
                        for path in existed_filepaths_on_client:
                            if path in tree_diff['new_on_client']:
                                if self._make_move_on_client(path, filepath, server_timestamp):
                                    tree_diff['new_on_client'].remove(path)
                                    break
                                else:
                                    self.stop(0, "move failed on in SYNC: src_path: {}, dest_path: {}".format(path, filepath))
                        # we haven't found files deleted on server so it's a copy
                        else:
                            if not self._make_copy_on_client(path, filepath, server_timestamp):
                                self.stop(0, "copy failed on in SYNC: src_path: {}, dest_path: {}".format(path, filepath))
                    else:
                        # it's a new file
                        sync_commands.append(('download', filepath))
                        # self.conn_mng.dispatch_request('download', {'filepath': filepath})

                for filepath in tree_diff['modified']:
                    sync_commands.append(('download', filepath))
                    # self.conn_mng.dispatch_request('download', {'filepath': filepath})

                for filepath in tree_diff['new_on_client']:
                    # files that have been deleted on server, so have to delete them
                    abs_filepath = self.absolutize_path(filepath)
                    self.observer.skip(abs_filepath)
                    try:
                        os.remove(abs_filepath)
                    except OSError as e:
                        print "Delete EXEPTION INTO SYNC : {}".format(e)

                    self.client_snapshot.pop(filepath)
                    self.update_local_dir_state(server_timestamp)

        return sync_commands

    def sync_with_server(self):
        """
        Makes the synchronization with server
        """
        response = self.conn_mng.dispatch_request('get_server_snapshot', '')
        if response is None:
            self.stop(1, '\nReceived None snapshot. Server down?\n')

        server_timestamp = response['server_timestamp']
        files = response['files']

        sync_commands = self._sync_process(server_timestamp, files)

        # Initialize the variable where we put the timestamp of the last operation we did
        last_operation_timestamp = server_timestamp

        # makes all synchronization commands
        for command, path in sync_commands:
            if command == 'delete':
                event_timestamp = self.conn_mng.dispatch_request(command, {'filepath': path})
                if event_timestamp:

                    last_operation_timestamp = event_timestamp['server_timestamp']
                    # If i can't find path inside client_snapshot there is inconsistent problem in client_snapshot!
                    if self.client_snapshot.pop(path, 'ERROR') == 'ERROR':
                        print 'Error during delete event INTO SYNC! Impossible to find "{}" inside client_snapshot'.format(
                            path)
                else:
                    self.stop(1,
                              'Error during connection with the server. Server fail to "delete" this file: {}'.format(
                                  path))

            elif command == 'modify' or command == 'upload':

                new_md5 = self.hash_file(self.absolutize_path(path))
                event_timestamp = self.conn_mng.dispatch_request(command, {'filepath': path, 'md5': new_md5})
                if event_timestamp:
                    last_operation_timestamp = event_timestamp['server_timestamp']
                else:
                    self.stop(1, 'Error during connection with the server. Server fail to "{}" this file: {}'.format(
                        command, path))

            else:  # command == 'download'
                print 'skip di download'
                self.observer.skip(self.absolutize_path(path))
                connection_result = self.conn_mng.dispatch_request(command, {'filepath': path})
                if connection_result:
                    print 'Downloaded file with path "{}" INTO SYNC'.format(path)                    
                    self.client_snapshot[path] = files[path]
                else:
                    self.stop(1,
                              'Error during connection with the server. Client fail to "download" this file: {}'.format(
                                  path))

        self.update_local_dir_state(last_operation_timestamp)

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

    def create_observer(self):
        """
        Create an instance of the watchdog Observer thread class.
        """
        self.observer = SkipObserver()
        self.observer.schedule(self, path=self.cfg['sharing_path'], recursive=True)

    # TODO handly erorrs in dictionary if the client_dispatcher miss required data!!
    # TODO update struct with new more performance data structure
    # TODO verify what happen if the server return a error message
    # ###################################

    def on_created(self, e):
        def build_data(cmd, rel_new_path, new_md5, founded_path=None):
            """
            Prepares the data from event handler to be delivered to connection_manager.
            """
            data = {'cmd': cmd}
            if cmd == 'copy':
                data['file'] = {'src': founded_path,
                                'dst': rel_new_path,
                                'md5': new_md5,
                            }
            else:
                data['file'] = {'filepath': rel_new_path,
                                'md5': new_md5,
                            }
            return data

        new_md5 = self.hash_file(e.src_path)
        rel_new_path = self.relativize_path(e.src_path)
        founded_path = self.search_md5(new_md5)

        # with this check i found the copy events
        if founded_path:
            print 'start copy'
            data = build_data('copy', rel_new_path, new_md5, founded_path)

        # this elif check that this created aren't modified event
        elif rel_new_path in self.client_snapshot:
            print 'start modified FROM CREATE!!!!!'
            data = build_data('modify', rel_new_path, new_md5)

        else:  # Finally we find a real create event!
            print 'start create'
            data = build_data('upload', rel_new_path, new_md5)

        # Send data to connection manager dispatcher and check return value. If all go right update client_snapshot and local_dir_state
        event_timestamp = self.conn_mng.dispatch_request(data['cmd'], data['file'])
        print 'event_timestamp di "{}" = {}'.format(data['cmd'], event_timestamp['server_timestamp'])
        if event_timestamp:
            self.client_snapshot[rel_new_path] = [event_timestamp['server_timestamp'], new_md5]
            self.update_local_dir_state(event_timestamp['server_timestamp'])
        else:
            self.stop(1, 'Impossible to connect with the server. Failed during "{0}" operation on "{1}" file'
                      .format(data['cmd'], e.src_path))

    def on_moved(self, e):

        print 'start move'
        rel_src_path = self.relativize_path(e.src_path)
        rel_dest_path = self.relativize_path(e.dest_path)
        # If i can't find rel_src_path inside client_snapshot there is inconsistent problem in client_snapshot!
        if self.client_snapshot.get(rel_src_path, 'ERROR') == 'ERROR':
            self.stop(1,
                      'Error during move event! Impossible to find "{}" inside client_snapshot'.format(rel_dest_path))
        md5 = self.client_snapshot[rel_src_path][1]
        data = {'src': rel_src_path,
                'dst': rel_dest_path,
                'md5': md5,
            }
        # Send data to connection manager dispatcher and check return value. If all go right update client_snapshot and local_dir_state
        event_timestamp = self.conn_mng.dispatch_request('move', data)
        print 'event_timestamp di "move" =', event_timestamp['server_timestamp']
        if event_timestamp:
            self.client_snapshot[rel_dest_path] = [event_timestamp['server_timestamp'], md5]
            # I'm sure that rel_src_path exists inside client_snapshot because i check above so i don't check pop result
            self.client_snapshot.pop(rel_src_path)
            self.update_local_dir_state(event_timestamp['server_timestamp'])
        else:
            self.stop(1, 'Impossible to connect with the server. Failed during "move" operation on "{}" file'.format(
                e.src_path))

    def on_modified(self, e):

        print 'start modified'
        new_md5 = self.hash_file(e.src_path)
        rel_path = self.relativize_path(e.src_path)

        data = {'filepath': rel_path,
                'md5': new_md5
            }

        # Send data to connection manager dispatcher and check return value. If all go right update client_snapshot and local_dir_state
        event_timestamp = self.conn_mng.dispatch_request('modify', data)
        if event_timestamp:
            print 'event_timestamp di "modified" =', event_timestamp['server_timestamp']
            self.client_snapshot[rel_path] = [event_timestamp['server_timestamp'], new_md5]
            self.update_local_dir_state(event_timestamp['server_timestamp'])
        else:
            self.stop(1, 'Impossible to connect with the server. Failed during "delete" operation on "{}" file'.format(
                e.src_path))

    def on_deleted(self, e):

        print 'start delete'
        rel_deleted_path = self.relativize_path(e.src_path)

        # Send data to connection manager dispatcher and check return value. If all go right update client_snapshot and local_dir_state
        event_timestamp = self.conn_mng.dispatch_request('delete', {'filepath': rel_deleted_path})
        if event_timestamp:
            print 'event_timestamp di "delete" =', event_timestamp['server_timestamp']
            # If i can't find rel_deleted_path inside client_snapshot there is inconsistent problem in client_snapshot!
            if self.client_snapshot.pop(rel_deleted_path, 'ERROR') == 'ERROR':
                print 'Error during delete event! Impossible to find "{}" inside client_snapshot'.format(
                    rel_deleted_path)
            self.update_local_dir_state(event_timestamp['server_timestamp'])
        else:
            self.stop(1, 'Impossible to connect with the server. Failed during "delete" operation on "{}" file'.format(
                e.src_path))

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

    def start(self):
        """
        Starts the communication with the command_manager.
        """
        self.build_client_snapshot()
        self.load_local_dir_state()

        # Operations necessary to start the daemon
        self.create_observer()
        self.observer.start()

        self.listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener_socket.bind((self.cfg['cmd_address'], self.cfg['cmd_port']))
        self.listener_socket.listen(self.cfg['backlog_listener_sock'])
        r_list = [self.listener_socket]
        self.daemon_state = 'started'
        self.running = 1
        polling_counter = 0
        self.sync_with_server()
        try:
            while self.running:
                r_ready, w_ready, e_ready = select.select(r_list, [], [], self.cfg['timeout_listener_sock'])

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
                                if cmd == 'shutdown':
                                    self._set_cmdmanager_response(s, 'Deamon is shuting down')
                                    raise KeyboardInterrupt
                                else:
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

                # synchronization polling
                # makes the polling every 3 seconds, so it waits six cycle (0.5 * 6 = 3 seconds)
                # maybe optimizable but now functional

                polling_counter += 1
                if polling_counter == 6:
                    polling_counter = 0
                    self.sync_with_server()

        except KeyboardInterrupt:
            self.stop(0)
        self.observer.stop()
        self.observer.join()
        self.listener_socket.close()

    def stop(self, exit_status, exit_message=None):
        """
        Stop the Daemon components (observer and communication with command_manager).
        """
        if self.daemon_state == 'started':
            self.running = 0
            self.daemon_state = 'down'
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
        json.dump(self.local_dir_state, open(self.cfg['local_dir_state_path'], "wb"), indent=4)
        print "local_dir_state saved"

    def load_local_dir_state(self):
        """
        Load local dir state on self.local_dir_state variable
        if file doesn't exists it will be created without timestamp
        """

        def _rebuild_local_dir_state():
            self.local_dir_state = {'last_timestamp': 0, 'global_md5': self.md5_of_client_snapshot()}
            json.dump(self.local_dir_state, open(self.cfg['local_dir_state_path'], "wb"), indent=4)

        if os.path.isfile(self.cfg['local_dir_state_path']):
            self.local_dir_state = json.load(open(self.cfg['local_dir_state_path'], "rb"))
            print "Loaded local_dir_state"
        else:
            print "local_dir_state not found. Initialize new local_dir_state"
            _rebuild_local_dir_state()


    def md5_of_client_snapshot(self, verbose=0):
        """
        Calculate the md5 of the entire directory snapshot,
        with the md5 in client_snapshot and the md5 of full filepath string.
        :return is the md5 hash of the directory
        """

        if verbose:
            start = time.time()
        md5Hash = hashlib.md5()
        
        for path, time_md5 in sorted(self.client_snapshot.items()):            
            # extract md5 from tuple. we don't need hexdigest it's already md5
            if verbose:
                print path
            md5Hash.update(time_md5[1])
            md5Hash.update(path)

        if verbose:
            stop = time.time()
            print stop - start
        return md5Hash.hexdigest()

    def hash_file(self, file_path, chunk_size=1024):
        """
        :accept an absolute file path
        :return the md5 hash of received file
        """

        md5Hash = hashlib.md5()
        try:
            f1 = open(file_path, 'rb')
            while 1:
                # Read file in as little chunks
                buf = f1.read(chunk_size)
                if not buf:
                    break
                md5Hash.update(buf)
            f1.close()
            return md5Hash.hexdigest()
        except (OSError, IOError) as e:
            print e
            return None


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-cfg", help="the configuration file filepath", type=str)
    
    args = parser.parse_args()
    
    daemon = Daemon(args.cfg)
    daemon.start()