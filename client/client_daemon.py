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

import connection_manager


class DirectoryMonitor(FileSystemEventHandler):
    """
    The DirectoryMonitor for file system events
    like: moved, deleted, created, modified
    """
    def __init__(self, folder_path, event_dispatcher):
        FileSystemEventHandler.__init__(self)
        self.event_dispatcher = event_dispatcher
        self.folder_path = folder_path
        self.folder_watched = self.folder_path.split(os.sep)[-1]
        self.observer = Observer()
        self.observer.schedule(self, path=folder_path, recursive=True)

    def on_any_event(self, event):
        """
        it catpures any filesytem event and redirects it to the event_dispatcher
        """
        def build_data(cmd,e):
            data = {}
            data['cmd'] = cmd
            data['file'] = {
                "filepath": self.relativize_path(e.src_path), 
                "mtime": os.path.getmtime(e.src_path), 
                "md5": hashlib.md5(e.src_path).h0exdigest()
            }         
            return data        
        
        if event.is_directory is False:        
            e = event           
            
            if e.event_type == 'modified':
                data = build_data('modify', e)

            elif e.event_type == 'created':
                data = build_data('upload', e)                

            elif e.event_type == 'moved':
                data = {'cmd':'move'}
                data['file'] = {
                    'src_path': self.relativize_path(e.src_path),
                    'dest_path': self.relativize_path(e.dest_path)}

            elif e.event_type == 'deleted':
                data = {'cmd':'delete'}
                data['file'] = {
                    "filepath": self.relativize_path(e.src_path)} 
            
            self.event_dispatcher(data['cmd'], data['file'])

    def relativize_path(self,path_to_clean):
        """ 
        This function relativize the path watched by watchdog:
        for example: /home/user/watched/subfolder/ will be subfolder/
        """
        cleaned_path = path_to_clean.split(self.folder_watched)[-1]
        # cleaned from first slash character
        return cleaned_path[1:]


    def start(self):
        """
        starts the observer thread
        """        
        self.observer.start()
        

    def stop(self):
        """
        stops the observer thread
        """
        self.observer.stop()

    def join(self):
        """
        waits for observer execution finalize
        """        
        self.observer.join()



class Daemon(object):
    """
    Root of all evil:
    it loads program configurations,
    it starts directory events observations
    it serves command manager
    """

    TIMEOUT = 0.5

    def __init__(self):
        self.cfg = load_json('config.json')
        if not self.cfg:
            print "No config File!"
            exit()           
        self.conn_mng = connection_manager.ConnectionManager(self.cfg)
        self.sync_with_server(self.cfg['sharing_path'])
        self.dir_manager = DirectoryMonitor(self.cfg['sharing_path'], self.event_dispatcher)
        self.running = 0

    def sync_with_server(self):
        """
        download from server the files state and find the difference from actual state
        """
        def download_files_state():
            """download from server the files state"""
            server_state = self.event_dispatcher('get_server_state')
            print server_state
            server_state = {'files': { '<path>': '<md5>'}}
            return server_state['files']
        
        def make_client_state():
            client_state = {}
            for dirpath, dirs, files in os.walk(self.cfg['sharing_path']):
            for filename in files:
                file_path = os.path.join(dirpath, filename)
                with open(file_path, 'rb') as fp:
                    md5_string = calculate_file_md5(fp)
                client_state[file_path] = md5_string
            return client_state

        server_state = download_files_state()
        client_state = make_client_state()
        for file_path in server_state:
            if file_path not in client_state[file_path]:
                # TODO files/crea
            else:
                if server_state[file_path] != client_state[file_path]:
                    pass # TODO files/aggiorna

    def cmd_dispatcher(self, data):
        """
        It dispatch cmd and args to the api manager object
        """
        cmd = data.keys()[0]  # it will be always one key
        args = data[cmd]  # it will be a dict specifying the args

        print cmd, args

        if cmd == 'shutdown':
            self.shutdown()
        else:
            self.conn_mng.dispatch_request(cmd, args)

    def event_dispatcher(self, cmd, data_file):
        """
        It dispatch the captured events to the api manager object
        """
        self.conn_mng.dispatch_request(cmd, data_file)

    def serve_forever(self):
        """
        it handles the dir manager thread and the server socket together
        """
        backlog = 5
        int_size = struct.calcsize('!i')

        listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener_socket.bind((self.cfg['host'], self.cfg['port']))
        listener_socket.listen(backlog)
        r_list = [listener_socket]

        self.dir_manager.start()

        self.running = 1
        try:
            while self.running:
                r_ready, w_ready, e_ready = select.select(r_list, [], [], self.TIMEOUT)

                for s in r_ready:

                    if s == listener_socket:
                        # handle the server socket
                        client_socket, client_address = listener_socket.accept()
                        r_list.append(client_socket)
                    else:
                        # handle all other sockets
                        length = s.recv(int_size)
                        if length:
                            length = int(struct.unpack('!i', length)[0])
                            data = json.loads(s.recv(length))
                            self.cmd_dispatcher(data)
                        else:
                            s.close()
                            r_list.remove(s)
        except KeyboardInterrupt:
            self.shutdown()

        self.dir_manager.join()
        listener_socket.close()

    def shutdown(self):
        self.dir_manager.stop()
        self.running = 0

def load_json(conf_path):
    if os.path.isfile(conf_path):
        with open(conf_path,"r") as fo:
            config = json.load(fo)
        return config
    else:
        return False

if __name__ == '__main__':

    daemon = Daemon()
    daemon.serve_forever()
