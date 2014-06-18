#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import socket
import struct
import select
import os
import hashlib

# we import PollingObserver instead of Observer because the deleted event
# is not capturing https://github.com/gorakhargosh/watchdog/issues/46
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler

from connection_manager import ConnectionManager

class Daemon(FileSystemEventHandler):

    # TODO : se non c'è crearla
    DEFAULT_CONFIG = {
    "sharing_path": "./sharing_folder", 
    "cmd_address": "localhost",
    "cmd_port": 50001,
    "api_suffix": "/API/V1/",
    "server_address":"http://localhost:5000",
    "user":"default_user",
    "pass":"default_pass",
    "timeout_listener_sock" : 0.5,
    "backlog_listener_sock" : 5
    }

    PATH_CONFIG = 'config.json'
    INT_SIZE = struct.calcsize('!i')

    def __init__(self):
        FileSystemEventHandler.__init__(self)
        # Initialize variable
        self.daemon_state = 'down' # TODO implement the daemon state( disconnected, connected, syncronizing, ready...)
        self.running = 0
        self.client_snapshot = {}
        self.listener_socket = None
        self.observer = None
        self.cfg = self.load_json(Daemon.PATH_CONFIG)
        self.conn_mng = ConnectionManager(self.cfg)
        # Operations necessary to start the daemon
        self.connect_to_server()
        self.build_client_snapshot()
        self.sync_with_server()
        self.create_observer()

    def load_json(self, conf_path):
        if os.path.isfile(conf_path):
            with open(conf_path,"r") as fo:
                config = json.load(fo)
            return config
        else:
            return self.DEFAULT_CONFIG

    def connect_to_server(self):
        # self.cfg['server_address']
        pass

    def build_client_snapshot(self):
        for dirpath, dirs, files in os.walk(self.cfg['sharing_path']):
                for filename in files:
                    file_path = os.path.join(dirpath, filename)
                    relative_file_path = self.relativize_path(file_path)
                    with open(file_path, 'rb') as f:
                        self.client_snapshot[relative_file_path] = hashlib.md5(f.read()).hexdigest()

    def sync_with_server(self):
        """
        Download from server the files state and find the difference from actual state.
        """

        server_snapshot = self.conn_mng.dispatch_request('get_server_snapshot')
        if server_snapshot is None:
            print('No snapshot. Server down?')
            return
        else:
            server_snapshot = server_snapshot['files']

        for file_path in server_snapshot:
            if file_path not in self.client_snapshot:
                # TODO : check if download succeed, if so update client_snapshot with the new file
                self.conn_mng.dispatch_request('download', {'filepath' : file_path } )
                self.client_snapshot[file_path] = server_snapshot[file_path]
            else:
                if server_snapshot[file_path] != self.client_snapshot[file_path]:
                    self.conn_mng.dispatch_request('modify', {'filepath' : file_path } )
        for file_path in self.client_snapshot:
            if file_path not in server_snapshot:
                self.conn_mng.dispatch_request('upload', {'filepath': file_path})

    def relativize_path(self, path_to_clean):
        """
        This function relativize the path watched by daemon:
        for example: /home/user/watched/subfolder/ will be subfolder/
        """
        folder_watched = self.cfg['sharing_path'].split(os.sep)[-1]
        cleaned_path = path_to_clean.split(folder_watched)[-1]
        # cleaned from first slash character
        return cleaned_path[1:]

    def create_observer(self):
        """
        Create an instance of the watchdog Observer thread class.
        """
        self.observer = Observer()
        self.observer.schedule(self, path=self.cfg['sharing_path'], recursive=True)

    def build_data(self, cmd, e, new_md5 = None):
        """
        Prepares the data from event handler to be delivered to connection_manager.
        """

        data = {'cmd' : cmd}
        if cmd == 'copy':
            for path in self.client_snapshot:
                if new_md5 in self.client_snapshot[path]: path_with_same_md5 = path
            data['file'] = {
            'src' : path_with_same_md5,
            'dst' : self.relativize_path(e.src_path),
            'md5' : self.client_snapshot[path_with_same_md5]
            }
        elif cmd == 'move':
            data['file'] = {
            'src' : self.relativize_path(e.src_path),
            'dst' : self.relativize_path(e.dest_path),
            'md5' : self.client_snapshot[self.relativize_path(e.src_path)]
            }
        elif cmd == 'delete':
            data['file'] = {
                'filepath': self.relativize_path(e.src_path),
                }
        else:
            f = open(e.src_path, 'rb')
            data['file'] = {
                'filepath': self.relativize_path(e.src_path),
                'md5' : hashlib.md5(f.read()).hexdigest()
                }
        return data

    def on_any_event(self, event):
        """
        Catpure any filesytem event and redirects it to the connection_manager.
        """

        # TODO update struct with new more performance data structure

        ####################################
        #### In client_snapshot the structure are {'<filepath>' : '<md5>'} so you have to convert!!!!
        ####################################

        if event.is_directory is False:
            e = event

            if e.event_type == 'modified':
                print 'start modified'
                data = self.build_data('modify', e)
                self.client_snapshot[data['file']['filepath']] = data['file']['md5']

            elif e.event_type == 'created':
                with open(e.src_path, 'rb') as f:
                        new_md5 = hashlib.md5(f.read()).hexdigest()
                # this check that the md5 doesn't exist, in that case is not a creation but a copy
                relative_path = self.relativize_path(e.src_path)

                if new_md5 in self.client_snapshot.values():
                    print 'start copy'
                    data = self.build_data('copy', e, new_md5)
                    self.client_snapshot[data['file']['dst']] = data['file']['md5']
                # this elif relative_path deny to overwrite file with the same path but md5 different
                # TODO FIX this case that happen with gedit
                elif relative_path in self.client_snapshot:
                    print 'start corrected created'
                    data = self.build_data('modify', e)
                    self.client_snapshot[data['file']['filepath']] = data['file']['md5']
                else:
                    print 'start create'
                    data = self.build_data('upload', e)
                    self.client_snapshot[data['file']['filepath']] = data['file']['md5']

            elif e.event_type == 'moved':
                print 'start move'
                data = self.build_data('move', e)
                self.client_snapshot[data['file']['dst']] = data['file']['md5']
                self.client_snapshot.pop(data['file']['src'])

            elif e.event_type == 'deleted':
                print 'start delete'
                data = self.build_data('delete', e)
                self.client_snapshot.pop(data['file']['filepath'])
            # TODO verify what happen if the server return a error message

            self.conn_mng.dispatch_request(data['cmd'], data['file'])

    def start(self):
        """
        Starts the communication with the command_manager.
        """

        self.listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener_socket.bind((self.cfg['cmd_address'], self.cfg['cmd_port']))
        self.listener_socket.listen(self.cfg['backlog_listener_sock'])
        r_list = [self.listener_socket]

        self.observer.start()

        self.running = 1
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
                            length = int(struct.unpack('!i', length)[0])
                            message = json.loads(s.recv(length))
                            for cmd, data in message.items():
                                if cmd == 'shutdown' : raise KeyboardInterrupt
                                self.conn_mng.dispatch_request(cmd, data)
                        else:
                            s.close()
                            r_list.remove(s)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """
        Stop the Daemon components (observer and communication with command_manager).
        """
        self.observer.stop()
        self.observer.join()
        self.listener_socket.close()
        self.running = 0


if __name__ == '__main__':

    daemon = Daemon()
    daemon.start()
