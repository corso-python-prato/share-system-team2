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

    def __init__(self, cfg, logging_level=logging.DEBUG):
        self.cfg = cfg
        self.auth = (self.cfg['user'], self.cfg['pass'])

        # example of self.base_url = 'http://localhost:5000/API/V1/'
        self.base_url = ''.join([self.cfg['server_address'], self.cfg['api_suffix']])
        self.files_url = ''.join([self.base_url, 'files/'])
        self.actions_url = ''.join([self.base_url, 'actions/'])
        self.shares_url = ''.join([self.base_url, 'shares/'])
        self.logging.basicConfig(level=logging_level)

    def dispatch_request(self, command, args=None):
        method_name = ''.join(['do_', command])
        try:
            return getattr(self, method_name)(args)
        except AttributeError:
            self._default(method_name)

    def do_reguser(self, data):
        data = {'username': data[0], 'password': data[1]}
        url = ''.join([self.base_url, 'signup'])
        self.logging.info('ConnectionManager: do_reguser: URL: {} - DATA: {} '.format(url, data))

        try:
            r = requests.post(url, data=data)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:            
            self.logging.error('ConnectionManager: do_reguser: URL: {} - EXCEPTIONS_CATCHED: {} '.format(url, e))
        else:
            return r.text
        return False

    # files

    def do_download(self, data):
        url = ''.join([self.files_url, data['filepath']])
        self.logging.info('ConnectionManager: do_download: URL: {} - DATA: {} '.format(url, data))

        try:
            r = requests.get(url, auth=self.auth)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logging.error('ConnectionManager: do_download: URL: {} - EXCEPTIONS_CATCHED: {} '.format(url, e))
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
        _file = {'file': (open(filepath, 'rb'))}
        self.logging.info('ConnectionManager: do_upload: URL: {} - DATA: {} '.format(url, data))
        try:
            r = requests.post(url, auth=self.auth, files=_file)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logging.error('ConnectionManager: do_upload: URL: {} - EXCEPTIONS_CATCHED: {} '.format(url, e))
        else:
            event_timestamp = r.text
            self.logging.error('ConnectionManager: do_upload: URL: {} - ResponseTxt: {} '.format(url, event_timestamp))
            return event_timestamp
        return False

    def do_modify(self, data):
        filepath = os.path.join(self.cfg['sharing_path'], data['filepath'])
        url = ''.join([self.files_url, data['filepath']])
        _file = {'file': (open(filepath, 'rb'))}
        self.logging.info('ConnectionManager: do_modify: URL: {} - DATA: {} '.format(url, data))
        try:
            r = requests.put(url, auth=self.auth, files=_file)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logging.error('ConnectionManager: do_modify: URL: {} - EXCEPTIONS_CATCHED: {} '.format(url, e))
        else:
            event_timestamp = r.text
            self.logging.error('ConnectionManager: do_modify: URL: {} - ResponseTxt: {} '.format(url, event_timestamp))
            return event_timestamp
        return False

    # actions:

    def do_move(self, data):
        url = ''.join([self.actions_url, 'move'])
        d = {'src': data['src'], 'dst': data['dst']}
        self.logging.info('ConnectionManager: do_move: URL: {} - DATA: {} '.format(url, data))
        try:
            r = requests.post(url, auth=self.auth, data=d)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logging.error('ConnectionManager: do_move: URL: {} - EXCEPTIONS_CATCHED: {} '.format(url, e))
        else:
            event_timestamp = r.text
            self.logging.error('ConnectionManager: do_move: URL: {} - ResponseTxt: {} '.format(url, event_timestamp))
            return event_timestamp
        return False

    def do_delete(self, data):
        url = ''.join([self.actions_url, 'delete'])
        self.logging.info('ConnectionManager: do_delete: URL: {} - DATA: {} '.format(url, data))
        d = {'filepath': data['filepath']}
        try:
            r = requests.post(url, auth=self.auth, data=d)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logging.error('ConnectionManager: do_delete: URL: {} - EXCEPTIONS_CATCHED: {} '.format(url, e))
        else:
            event_timestamp = r.text
            self.logging.error('ConnectionManager: do_delete: URL: {} - ResponseTxt: {} '.format(url, event_timestamp))
            return event_timestamp
        return False

    def do_copy(self, data):
        url = ''.join([self.actions_url, 'copy'])
        d = {'src': data['src'], 'dst': data['dst']}
        self.logging.info('ConnectionManager: do_copy: URL: {} - DATA: {} '.format(url, data))
        try:
            r = requests.post(url, auth=self.auth, data=d)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logging.error('ConnectionManager: do_copy: URL: {} - EXCEPTIONS_CATCHED: {} '.format(url, e))
        else:
            event_timestamp = r.text
            self.logging.error('ConnectionManager: do_copy: URL: {} - ResponseTxt: {} '.format(url, event_timestamp))
            return event_timestamp
        return False

    def do_get_server_snapshot(self, data):
        url = self.files_url
        self.logging.info('ConnectionManager: do_get_server_snapshot: URL: {} - DATA: {} '.format(url, data))
        try:
            r = requests.get(url, auth=self.auth)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logging.error('ConnectionManager: do_get_server_snapshot: URL: {} - EXCEPTIONS_CATCHED: {} '.format(url, e))
            if 'UNAUTHORIZED' in e[0]:
                self.do_reguser(('pasquale', 'secretpass'))
                return self.do_get_server_snapshot(data)
        else:
            return json.loads(r.text)

    def _default(self, method):
        print 'Received Unknown Command:', method