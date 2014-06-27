#!/usr/bin/env python
# -*- coding: utf-8 -*-

# API:
#
# files:
#  - GET /files/ - ottiene la lista dei file sul server con relativi metadati necessari e/o md5
#  - GET /files/<path> - scarica un file
#  - POST /files/<path> - crea un file
#  - PUT /files/<path> - modifica un file
# actions:
#  - POST /actions/copy - parametri src, dest
#  - POST /actions/delete - parametro path
#  - POST /actions/move - parametri src, dest
# ---------
# shares:
#  - POST /shares/<root_path>/<user> - crea (se necessario) lo share, e l’utente che “vede” la condivisione
#  - DELETE /shares/<root_path> - elimina del tutto lo share
#  - DELETE /shares/<root_path>/<user> - elimina l’utente dallo share

import requests
import json
import os
import logging

class ConnectionManager(object):
    EXCEPTIONS_CATCHED = (requests.HTTPError,
                          requests.exceptions.ConnectionError,
                          requests.exceptions.MissingSchema,
                          )

    def __init__(self, cfg, logging_level=logging.INFO):
        self.cfg = cfg
        self.auth = (self.cfg['user'], self.cfg['pass'])

        # example of self.base_url = 'http://localhost:5000/API/V1/'
        self.base_url = ''.join([self.cfg['server_address'], self.cfg['api_suffix']])
        self.files_url = ''.join([self.base_url, 'files/'])
        self.actions_url = ''.join([self.base_url, 'actions/'])
        self.shares_url = ''.join([self.base_url, 'shares/'])
        
        self.logger = logging.getLogger("ConMng")
        self.logger.setLevel(level=logging_level)
        # create a file handler

        handler = logging.FileHandler('test_connection_manager.log')
        handler.setLevel(logging_level)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        console_handler = logging.StreamHandler()        
        console_handler.setLevel(logging_level)        

        console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)       
        
        self.logger.addHandler(console_handler)

    def dispatch_request(self, command, args=None):
        method_name = ''.join(['do_', command])
        try:
            return getattr(self, method_name)(args)
        except AttributeError:
            self._default(method_name)

    def do_reguser(self, data):
        data = {'username': data[0], 'password': data[1]}
        url = ''.join([self.base_url, 'signup'])
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_reguser',url, data))

        try:
            r = requests.post(url, data=data)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:            
            pass
        else:
            return r.text
        return False

    # files

    def do_download(self, data):
        url = ''.join([self.files_url, data['filepath']])        
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_download',url, data))
        try:
            r = requests.get(url, auth=self.auth)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            pass
        else:
            filepath = os.path.join(self.cfg['sharing_path'], data['filepath'])
            dirpath, filename = os.path.split(filepath)
            if not os.path.exists(dirpath):
                # Create all missing directories
                os.makedirs(dirpath)
            with open(filepath, 'wb') as f:
                f.write(r.content)
            return True
        return False

    def do_upload(self, data):
        filepath = os.path.join(self.cfg['sharing_path'], data['filepath'])
        url = ''.join([self.files_url, data['filepath']])
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_upload',url, data))
        _file = {'file': (open(filepath, 'rb'))}
        
        try:
            r = requests.post(url, auth=self.auth, files=_file)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            pass
        else:
            event_timestamp = r.text
            
            return event_timestamp
        return False

    def do_modify(self, data):
        filepath = os.path.join(self.cfg['sharing_path'], data['filepath'])
        url = ''.join([self.files_url, data['filepath']])
        
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_modify',url, data))

        _file = {'file': (open(filepath, 'rb'))}        
        try:
            r = requests.put(url, auth=self.auth, files=_file)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            pass
        else:
            event_timestamp = r.text
            
            return event_timestamp
        return False

    # actions:

    def do_move(self, data):
        url = ''.join([self.actions_url, 'move'])
        d = {'src': data['src'], 'dst': data['dst']}
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_move',url, data))
        try:
            r = requests.post(url, auth=self.auth, data=d)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            pass
        else:
            event_timestamp = r.text
            
            return event_timestamp
        return False

    def do_delete(self, data):
        url = ''.join([self.actions_url, 'delete'])
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_delete',url, data))
        d = {'filepath': data['filepath']}
        try:
            r = requests.post(url, auth=self.auth, data=d)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            pass
        else:
            event_timestamp = r.text
            
            return event_timestamp
        return False

    def do_copy(self, data):
        url = ''.join([self.actions_url, 'copy'])
        d = {'src': data['src'], 'dst': data['dst']}
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_copy',url, data))
        try:
            r = requests.post(url, auth=self.auth, data=d)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            pass
        else:
            event_timestamp = r.text
            
            return event_timestamp
        return False

    def do_get_server_snapshot(self, data):
        url = self.files_url
        
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_get_server_snapshot',url, data))
        try:
            r = requests.get(url, auth=self.auth)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            
            if 'UNAUTHORIZED' in e[0]:
                self.do_reguser(('pasquale', 'secretpass'))
                return self.do_get_server_snapshot(data)
        else:
            return json.loads(r.text)

    #logging.info('ConnectionManager: do_reguser: URL: {} - DATA: {} '.format(url, data))
    #logging.error('ConnectionManager: do_reguser: URL: {} - EXCEPTIONS_CATCHED: {} '.format(url, e))

    def _default(self, method):
        print 'Received Unknown Command:', method