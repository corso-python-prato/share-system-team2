#!/usr/bin/env python
#-*- coding: utf-8 -*-
import sys
import os
import argparse
import json
import socket
import struct
import select


#!/usr/bin/env python
#-*- coding: utf-8 -*-
import time
# we import PollingObserver instead of Observer because the deleted event
# is not capturing https://github.com/gorakhargosh/watchdog/issues/46
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import LoggingEventHandler
from watchdog.events import FileSystemEventHandler
from threading import Thread

class DirectoryMonitor(FileSystemEventHandler):
    """ The DirectoryMonitor for file system events 
        like: moved, deleted, created, modified
    """
    def __init__(self):
        FileSystemEventHandler.__init__(self)
        self.observer = Observer()
        self.observer.schedule(self, path='/home/pasquale/', recursive=True)

    def on_any_event(self, event):
        self.event_handler(event)
    
    def event_handler(self,event):
        if event.is_directory == False:
            print event.src_path,event.event_type

    def start(self):    
        
        
        self.observer.start()
        try:   
            while True:
                time.sleep(1)            
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()

    def stop(self):
        self.observer.stop() 


def dispatcher(data):
    """It dispatch cmd and args to the api manager object"""

    cmd = data.keys()[0]  # it will be always one key
    args = data[cmd]  # it will be a dict specifying the args
    print cmd, args
    
def serve_forever():
    """ The localserver listener for the cmd manager """
    # fix-it: import info from config file
    host = 'localhost'
    port = 50001
    backlog = 5
    int_size = struct.calcsize('!i')

    deamon_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    deamon_server.bind((host, port))
    deamon_server.listen(backlog)
    r_list = [deamon_server]

    running = 1
    while running:
        r_ready, w_ready, e_ready = select.select(r_list, [], [], 0.5)

        for s in r_ready:

            if s == deamon_server:
                # handle the server socket
                client, address = deamon_server.accept()
                r_list.append(client)
            else:
                # handle all other sockets
                lenght = s.recv(int_size)
                if lenght:
                    lenght = int(struct.unpack('!i', lenght)[0])
                    data = s.recv(lenght)
                    data = json.loads(data)
                    dispatcher(data)
                else:
                    s.close()
                    r_list.remove(s)
    deamon_server.close()


if __name__ == '__main__':
    
    #first thread is the dirmonitor
    thread = Thread(target = DirectoryMonitor().start)
    thread.start()

    #second thread is the localserver for the cmd_manager
    thread2 = Thread(target = serve_forever)
    thread2.start()