#!/usr/bin/env python
#-*- coding: utf-8 -*-
import sys
import os
import argparse
import time
import requests
import json


# we import PollingObserver instead of Observer because the deleted event
# is not capturing https://github.com/gorakhargosh/watchdog/issues/46
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import LoggingEventHandler
from watchdog.events import FileSystemEventHandler


class Sync(object):
    METHODS = {"put": requests.put,
        "delete": requests.delete,
        "get": requests.get,
        "post": requests.post}

    def __init__(self, server_address):
        self.server_address = server_address

    def handler(self, event):
        try:
            if event.event_type == "modified":
               self.make_request("put")
            elif event.event_type == "deleted":
               self.make_request("delete")
            elif event.event_type == "created":
               self.make_request("post")
            elif event.event_type == "moved":
               self.make_request("delete")
        except (requests.HTTPError,requests.exceptions.ConnectionError,
                requests.exceptions.MissingSchema) as e:
            print e

    def make_request(self, kind, params=None):
        r = Sync.METHODS[kind](self.server_address)               
        r.raise_for_status()
        return r


class DirectoryMonitor(FileSystemEventHandler):
    """ Daemon Monitor for file system events 
        like: moved, deleted, created, modified
    """
    def __init__(self, callback):
        FileSystemEventHandler.__init__(self)
        self.callback = callback
        
    def catch_all(self, event):
        """ Dispatcher events.
        """
        self.callback(event)        

    def on_created(self, event):
         self.catch_all(event)        

    def on_deleted(self, event):        
         self.catch_all(event)

    def on_modified(self, event):
        self.catch_all(event)

    def on_moved(self, event):
        self.catch_all(event)  


def load_json(conf_path):
    if os.path.isfile(conf_path):
        with open(conf_path,"r") as fo:
             config = json.load(fo)
        return config
    else:
        "There's not the config file"


if __name__ == "__main__":
    conf = load_json("config.json")
    if os.path.isdir(conf["path"]):      
        
        sync = Sync(conf["server_address"]).handler
        event_handler = DirectoryMonitor(sync)
        observer = Observer()

        observer.schedule(event_handler, path=conf["path"], recursive=True)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    
    else:
        print "Directory inesistente."