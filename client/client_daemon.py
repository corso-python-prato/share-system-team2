#!/usr/bin/env python
#-*- coding: utf-8 -*-
import sys
import os
import argparse
import time
import requests

# we import PollingObserver instead of Observer because the deleted event
# is not capturing https://github.com/gorakhargosh/watchdog/issues/46
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import LoggingEventHandler
from watchdog.events import FileSystemEventHandler

class DirectoryMonitor(FileSystemEventHandler):
    """ Daemon Monitor for file system events 
        like moved deleted created modified
    """

    def __init__(self):
        FileSystemEventHandler.__init__(self)
        
    def catch_all(self,event, method_to_call):
        print event.event_type
        print event.src_path
        print event.is_directory        
        response = method_to_call('http://127.0.0.1:5000/api/v1/')        

    def on_created(self, event):        
        self.catch_all(event, requests.put)        

    def on_deleted(self, event):        
        self.catch_all(event, requests.delete)

    def on_modified(self, event):
        self.catch_all(event, requests.put)

    def on_moved(self, event):
        self.catch_all(event, requests.put)  



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Daemon watchdog.')
    parser.add_argument('path', help='Path to monitoring.')
    args = parser.parse_args()
    if os.path.isdir(args.path):
        event_handler = DirectoryMonitor()
        observer = Observer()

        observer.schedule(event_handler, path=args.path, recursive=True)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    else:
        print "Directory inesistente."
