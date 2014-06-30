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
                print 'Questa e\' _SKIP_LIST: ', self._skip_list, self._skip_list, 'Evento che chiama SKIP_LIST:', event
                print '\n\nSkipped event "{}" \non path: {}\n\n'.format(event, event.dest_path)
                self._skip_list.remove(event.dest_path)
                skip = True
        try:
            event.src_path
        except AttributeError:
            pass
        else:
            if event.src_path in self._skip_list:
                print 'Questa e\' _SKIP_LIST: ', self._skip_list, self._skip_list, 'Evento che chiama SKIP_LIST:', event
                print '\nSkipped event "{}" \n on path: {}\n'.format(event, event.src_path)
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
    DEF_CONF['local_dir_state_path'] = os.path.join(CONFIG_DIR,'local_dir_state')
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

    def __init__(self):
        RegexMatchingEventHandler.__init__(self, ignore_regexes=Daemon.IGNORED_REGEX, ignore_directories=True)

        # Just Initialize variable the Daemon.start() do the other things
        self.daemon_state = 'down'  # TODO implement the daemon state (disconnected, connected, syncronizing, ready...)
        self.running = 0
        self.client_snapshot = {} # EXAMPLE {'<filepath1>: ['<timestamp>', '<md5>', '<filepath2>: ...}
        self.local_dir_state = {} # EXAMPLE {'last_timestamp': '<timestamp>', 'global_md5': '<md5>'}
        self.listener_socket = None
        self.observer = None
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
                print '\nImpossible to read "{0}"! Config file overwrited and loaded default config!\n'.format(config_path)
                return build_default_cfg()
            corrupted_config = False
            for k in Daemon.DEF_CONF:
                if k not in loaded_config:
                    corrupted_config = True
            # In the case is all gone right run config in loaded_config
            if not corrupted_config:
                return loaded_config
            else:
                print '\nWarning "{0}" corrupted! Config file overwrited and loaded default config!\n'.format(config_path)
                return build_default_cfg()
        else:
            print '\nWarning "{0}" doesn\'t exist, Config file overwrited and loaded default config!\n'.format(config_path)
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
                self.stop(1, '\nImpossible to create "{0}" directory! Check sharing_path value contained in the following file:\n"{1}"\n'
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
                    with open(filepath, 'rb') as f:
                        self.client_snapshot[relative_path] = ['', hashlib.md5(f.read()).hexdigest()]

    def _is_directory_modified(self):
        if self.calculate_md5_of_dir() != self.local_dir_state['global_md5']:
            return True
        else:
            return False

    def search_md5(self, searched_md5):
        """
        Recive as parameter the md5 of a file and return the first knowed path with the same md5
        """
        for path, tupla in self.client_snapshot.iteritems():
            if searched_md5 in tupla[1]:
                return path
        else:
            return None

    def _sync_process(self, server_timestamp, server_dir_tree):
        # Makes the synchronization logic and return a list of commands to launch
        # for server synchronization

        def _filter_tree_difference(server_dir_tree):
            # process local dir_tree and server dir_tree
            # and makes a diffs classification
            # return a dict representing that classification
            # E.g. { 'new_on_server'     : <[<filepath>, ...]>,  # files in server, but not in client
            #   'modified'          : <[<filepath>, ...]>,  # files in server and client, but different
            #   'new_on_client'     : <[<filepath>, ...]>,  # files not in server, but in client
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

        def _make_copy(src, dst):
            abs_src = self.absolutize_path(src)
            abs_dst = self.absolutize_path(dst)
            self.observer.skip(abs_dst)
            try:
                copy2(abs_src, abs_dst)
            except IOError:
                return False

            self.client_snapshot[dst] = self.client_snapshot[src]
            return True

        def _make_move(src, dst):
            abs_src = self.absolutize_path(src)
            abs_dst = self.absolutize_path(dst)
            self.observer.skip(abs_dst)
            try:
                move(abs_src, abs_dst)
            except IOError:
                return False

            self.client_snapshot[dst] = self.client_snapshot[src]
            self.client_snapshot.pop(src)
            return True

        def _check_md5(dir_tree, md5):
            for k, v in dir_tree.items():
                if md5 == v[1]:
                    return k
            return None

        local_timestamp = self.local_dir_state['last_timestamp']
        tree_diff = _filter_tree_difference(server_dir_tree)

        sync_commands = []

        if self._is_directory_modified():
            if local_timestamp == server_timestamp:
                # simple case: the client has the command
                # it sends all folder modifications to server

                # files in server but not in client: remove them from server
                for filepath in tree_diff['new_on_server']:
                    sync_commands.append(('delete', filepath))
                    #self.conn_mng.dispatch_request('delete', {'filepath': filepath})

                # files modified in client: send modified files to server
                for filepath in tree_diff['modified']:
                    sync_commands.append(('modified', filepath))
                    #self.conn_mng.dispatch_request('modified', {'filepath': filepath})

                # files in client but not in server: upload them to server
                for filepath in tree_diff['new_on_client']:
                    sync_commands.append(('upload', filepath))
                    #self.conn_mng.dispatch_request('upload', {'filepath': filepath})

            else:  # local_timestamp < server_timestamp
                # the server has the command
                for filepath in tree_diff['new_on_server']:
                    timestamp, md5 = server_dir_tree[filepath]
                    existed_filepath = _check_md5(self.client_snapshot, md5)

                    if existed_filepath:
                        # it's a copy or a move
                        if _check_md5(server_dir_tree, md5):
                            _make_copy(existed_filepath, filepath)
                        else:
                            _make_move(existed_filepath, filepath)
                            tree_diff['new_on_client'].remove(filepath)
                    else:
                        if timestamp > local_timestamp:
                            # the files in server is more updated
                            sync_commands.append(('download', filepath))
                            #self.conn_mng.dispatch_request('download', {'filepath': filepath})
                        else:
                            # the client has deleted the file, so delete it on server
                            sync_commands.append(('delete', filepath))
                            #self.conn_mng.dispatch_request('delete', {'filepath': filepath})

                for filepath in tree_diff['modified']:
                    timestamp, md5 = server_dir_tree[filepath]

                    if timestamp < local_timestamp:
                        # the client has modified the file, so update it on server
                        sync_commands.append(('modify', filepath))
                        #self.conn_mng.dispatch_request('modify', {'filepath': filepath})
                    else:
                        # it's the worst case:
                        # we have a conflict with server,
                        # someone has modified files while daemon was down and someone else has modified
                        # the same file on server
                        conflicted_path = ''.join([filepath, '.conflicted'])
                        _make_copy(filepath, conflicted_path)
                        sync_commands.append(('upload', conflicted_path))
                        #self.conn_mng.dispatch_request('upload', {'filepath': conflicted_path})

                for filepath in tree_diff['new_on_client']:
                    sync_commands.append(('upload', filepath))
                    #self.conn_mng.dispatch_request('upload', {'filepath': filepath})

        else:  # directory not modified
            if local_timestamp == server_timestamp:
                # it's the best case. Client and server are already synchronized
                return []
            else:  # local_timestamp < server_timestamp
                # the server has the command
                for filepath in tree_diff['new_on_server']:
                    timestamp, md5 = server_dir_tree[filepath]
                    existed_filepath = _check_md5(self.client_snapshot, md5)

                    if existed_filepath:
                        # it's a copy or a move
                        if _check_md5(server_dir_tree, md5):
                            _make_copy(existed_filepath, filepath)
                        else:
                            _make_move(existed_filepath, filepath)
                            tree_diff['new_on_client'].remove(filepath)
                    else:
                        # it's a new file
                        sync_commands.append(('download', filepath))
                        #self.conn_mng.dispatch_request('download', {'filepath': filepath})

                for filepath in tree_diff['modified']:
                    sync_commands.append(('download', filepath))
                    #self.conn_mng.dispatch_request('download', {'filepath': filepath})

                for filepath in tree_diff['new_on_client']:
                    # files that have been deleted on server, so have to delete them
                    abs_filepath = self.absolutize_path(filepath)
                    self.observer.skip(abs_filepath)
                    try:
                        os.remove(abs_filepath)
                    except OSError:
                        # it should raise an exceptions
                        pass
                    self.client_snapshot.pop(filepath)

        return sync_commands

    def sync_with_server(self):
        """
        Makes the synchronization with server
        """
        response = self.conn_mng.dispatch_request('get_server_snapshot', '')
        if response is None:
            self.stop(1, '\nReceived bad snapshot. Server down?\n')
        else:
            server_timestamp = response['server_timestamp']
            files = response['files']

        sync_commands = self._sync_process(server_timestamp, files)

        # makes all synchronization commands
        for command, path in sync_commands:
            if command == 'delete':
                self.client_snapshot.pop(path)
            elif command == 'download' or command == 'modified':
                self.client_snapshot[path] = (server_timestamp, files[path][1])
                self.observer.skip(self.absolutize_path(path))
            self.conn_mng.dispatch_request(command, {'filepath': path})

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
    ####################################

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

        else: # Finally we find a real create event!
            print 'start create'
            data = build_data('upload', rel_new_path, new_md5)

        # Send data to connection manager dispatcher and check return value. If all go right update client_snapshot and local_dir_state
        event_timestamp = self.conn_mng.dispatch_request(data['cmd'], data['file'])
        print 'event_timestamp di "{}" = {}'.format(data['cmd'], event_timestamp)
        if event_timestamp:
            self.client_snapshot[rel_new_path] = [event_timestamp, new_md5]
            self.update_local_dir_state(event_timestamp['server_timestamp'])
        else:
            self.stop(1, 'Impossible to connect with the server. Failed during "{0}" operation on "{1}" file'
                      .format(data['cmd'], e.src_path ))

    def on_moved(self, e):

        print 'start move'
        rel_src_path = self.relativize_path(e.src_path)
        rel_dest_path = self.relativize_path(e.dest_path)
        # If i can't find rel_src_path inside client_snapshot there is inconsistent problem in client_snapshot!
        if self.client_snapshot.get(rel_src_path, 'ERROR') != 'ERROR':
            md5 = self.client_snapshot[rel_src_path][1]
        else:
            self.stop(1, 'Error during move event! Impossible to find "{}" inside client_snapshot'.format(rel_dest_path))

        data = {'src': rel_src_path,
                 'dst': rel_dest_path,
                 'md5': md5,
                 }
        # Send data to connection manager dispatcher and check return value. If all go right update client_snapshot and local_dir_state
        event_timestamp = self.conn_mng.dispatch_request('move', data)
        print 'event_timestamp di "move" =', event_timestamp
        if event_timestamp:
            self.client_snapshot[rel_dest_path] = [event_timestamp, md5]
            # I'm sure that rel_src_path exists inside client_snapshot because i check above so i don't check pop result
            self.client_snapshot.pop(rel_src_path)
            self.update_local_dir_state(event_timestamp['server_timestamp'])
        else:
            self.stop(1, 'Impossible to connect with the server. Failed during "move" operation on "{}" file'.format(e.src_path ))

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
            print 'event_timestamp di "modified" =', event_timestamp
            self.client_snapshot[rel_path] = [event_timestamp, new_md5]
            self.update_local_dir_state(event_timestamp['server_timestamp'])
        else:
            self.stop(1, 'Impossible to connect with the server. Failed during "delete" operation on "{}" file'.format(e.src_path))

    def on_deleted(self, e):

        print 'start delete'
        rel_deleted_path = self.relativize_path(e.src_path)

        # Send data to connection manager dispatcher and check return value. If all go right update client_snapshot and local_dir_state
        event_timestamp = self.conn_mng.dispatch_request('delete', {'filepath': rel_deleted_path})
        if event_timestamp:
            print 'event_timestamp di "delete" =', event_timestamp
            # If i can't find rel_deleted_path inside client_snapshot there is inconsistent problem in client_snapshot!
            if self.client_snapshot.pop(rel_deleted_path, 'ERROR') != 'ERROR':
            else:
                self.stop(1, 'Error during delete event! Impossible to find "{}" inside client_snapshot'.format(rel_deleted_path))
            self.update_local_dir_state(event_timestamp['server_timestamp'])
        else:
            self.stop(1, 'Impossible to connect with the server. Failed during "delete" operation on "{}" file'.format(e.src_path))

    def start(self):
        """
        Starts the communication with the command_manager.
        """
        self.build_client_snapshot()
        self.load_local_dir_state()

        # Operations necessary to start the daemon
        self.create_observer()
        self.observer.start()
        self.sync_with_server()

        self.listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener_socket.bind((self.cfg['cmd_address'], self.cfg['cmd_port']))
        self.listener_socket.listen(self.cfg['backlog_listener_sock'])
        r_list = [self.listener_socket]
        self.daemon_state = 'started'
        self.running = 1
        polling_counter = 0
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
                        length = s.recv(Daemon.INT_SIZE)
                        if length:
                            # i need to do [0] and cast int because the struct.unpack return a tupla like (23234234,)
                            # with the length as a string
                            length = int(struct.unpack('!i', length)[0])
                            message = json.loads(s.recv(length))
                            for cmd, data in message.items():
                                if cmd == 'shutdown':
                                    raise KeyboardInterrupt
                                self.conn_mng.dispatch_request(cmd, data)
                        else:
                            s.close()
                            r_list.remove(s)

                # synchronization polling
                # makes the polling every 3 seconds, so it waits six cycle (0.5 * 6 = 3 seconds)
                # maybe optimizable but now functional
                polling_counter += 1
                if polling_counter == 6:
                    self.sync_with_server()
                    polling_counter = 0

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
            self.daemon_state == 'down'
        self.save_local_dir_state()
        if exit_message:
            print exit_message
        exit(exit_status)

    def update_local_dir_state(self, last_timestamp):
        """
        Update the local_dir_state with last_timestamp operation and save it on disk
        """
        if isinstance(last_timestamp, int):
            self.local_dir_state['last_timestamp'] = last_timestamp
            self.local_dir_state['global_md5'] = self.calculate_md5_of_dir()
            self.save_local_dir_state()
        else:
            self.stop(1, 'Not int value assigned to local_dir_state[\'last_timestamp\']!\nIncorrect value: {}'.format(last_timestamp))

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
            self.local_dir_state = {'last_timestamp': 0.0, 'global_md5': self.calculate_md5_of_dir()}
            json.dump(self.local_dir_state, open(self.cfg['local_dir_state_path'], "wb"), indent=4)

        if os.path.isfile(self.cfg['local_dir_state_path']):
            self.local_dir_state = json.load(open(self.cfg['local_dir_state_path'], "rb"))
            if 'last_timestamp' in self.local_dir_state and 'global_md5' in self.local_dir_state \
                    and isinstance(self.local_dir_state['last_timestamp'], int):
                print "questo è last_timestamp:", self.local_dir_state['last_timestamp']
                #self.local_dir_state['last_timestamp'] = int(self.local_dir_state['last_timestamp'])
                print "Loaded local_dir_state"
            else:
                print "local_dir_state corrupted. Reinitialized new local_dir_state"
                _rebuild_local_dir_state()
        else:
            print "local_dir_state not found. Initialize new local_dir_state"
            _rebuild_local_dir_state()


    def calculate_md5_of_dir(self, verbose=0):
        """
        Calculate the md5 of the entire directory,
        with the md5 in client_snapshot and the md5 of full filepath string.
        When the filepath isn't in client_snapshot the md5 is calculated on fly
        :return is the md5 hash of the directory
        """
        directory = self.cfg['sharing_path']
        if verbose:
            start = time.time()
        md5Hash = hashlib.md5()
        if not os.path.exists(directory):
            self.stop(1, 'Error during calculate md5! Impossible to find "{}" in user folder'.format(directory))

        for root, dirs, files in os.walk(directory, followlinks=False):
            for names in files:
                filepath = os.path.join(root, names)
                rel_path = self.relativize_path(filepath)
                if rel_path in self.client_snapshot:
                    md5Hash.update(self.client_snapshot[rel_path][1])
                    md5Hash.update(hashlib.md5(filepath).hexdigest())
                else:
                    hashed_file = self.hash_file(filepath)
                    if hashed_file:
                        md5Hash.update(hashed_file)
                        md5Hash.update(hashlib.md5(filepath).hexdigest())
                    else:
                        print "can't hash file: ", filepath

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
                    md5Hash.update(hashlib.md5(buf).hexdigest())
            f1.close()
            return md5Hash.hexdigest()
        except (OSError, IOError) as e:
            print e
            return None
            # You can't open the file for some reason

if __name__ == '__main__':
    daemon = Daemon()
    daemon.start()