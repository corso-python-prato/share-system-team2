#!/usr/bin/env python
#-*- coding: utf-8 -*-

import json
import socket
import struct
import select

# we import PollingObserver instead of Observer because the deleted event
# is not capturing https://github.com/gorakhargosh/watchdog/issues/46
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler


class DirectoryMonitor(FileSystemEventHandler):
    """
    The DirectoryMonitor for file system events
    like: moved, deleted, created, modified
    """
    def __init__(self, folder_path, callback):
        FileSystemEventHandler.__init__(self)
        self.callback = callback
        self.observer = Observer()
        self.observer.schedule(self, path=folder_path, recursive=True)

    def on_any_event(self, event):
        """
        it catpures any filesytem event and redirects it to the callback
        """
        if event.is_directory == False:
            self.callback(event)

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
        self.cfg = json.loads(open('config.json', 'r').read())
        # self.api = Api()
        self.dir_manager = DirectoryMonitor(self.cfg['path'], self.event_dispatcher)
        self.running = 0


    def cmd_dispatcher(self, data):
        """
        It dispatch cmd and args to the api manager object
        """
        cmd = data.keys()[0]  # it will be always one key
        args = data[cmd]  # it will be a dict specifying the args

        if cmd == 'stop':
            self.stop()
        print cmd, args
        # self.api.send(cmd, args)

    def event_dispatcher(self, event):
        """
        It dispatch the captured events to the api manager object
        """
        print event  # fix-it

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
        while self.running:
            r_ready, w_ready, e_ready = select.select(r_list, [], [], self.TIMEOUT)

            for s in r_ready:

                if s == listener_socket:
                    # handle the server socket
                    client_socket, client_address = listener_socket.accept()
                    r_list.append(client_socket)
                else:
                    # handle all other sockets
                    lenght = s.recv(int_size)
                    if lenght:
                        lenght = int(struct.unpack('!i', lenght)[0])
                        data = s.recv(lenght)
                        data = json.loads(data)
                        self.cmd_dispatcher(data)
                    else:
                        s.close()
                        r_list.remove(s)

        self.dir_manager.join()
        listener_socket.close()

    def stop(self):
        self.dir_manager.stop()
        self.running = 0

if __name__ == '__main__':

    daemon = Daemon()
    daemon.serve_forever()