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


class ConnectionManager(object):
    EXCEPTIONS_CATCHED = (requests.HTTPError,
                          requests.exceptions.ConnectionError,
                          requests.exceptions.MissingSchema,
                          )

    def __init__(self, cfg):
        self.cfg = cfg
        self.auth = (self.cfg['user'], self.cfg['pass'])

        # example of self.base_url = 'http://localhost:5000/API/V1/'
        self.base_url = ''.join([self.cfg['server_address'], self.cfg['api_suffix']])
        self.files_url = ''.join([self.base_url, 'files/'])
        self.actions_url = ''.join([self.base_url, 'actions/'])
        self.shares_url = ''.join([self.base_url, 'shares/'])

    def dispatch_request(self, command, args=None):
        method_name = ''.join(['do_', command])
        try:
            return getattr(self, method_name)(args)
        except AttributeError:
            self._default(method_name)

    def do_reguser(self, data):
        data = {'username': data[0], 'password': data[1]}
        url = ''.join([self.base_url, 'signup'])
        print 'do_reguser', url, data
        try:
            r = requests.post(url, data=data)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            print 'Errore REGUSER: ', url, 'Codice Errore: ', e
        else:
            return r.text
        return False

    # files

    def do_download(self, data):
        url = ''.join([self.files_url, data['filepath']])
        print 'do_download', url

        try:
            r = requests.get(url, auth=self.auth)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            print 'Errore DOWNLOAD: ', url, 'Codice Errore: ', e
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
        print 'do_upload', url
        try:
            r = requests.post(url, auth=self.auth, files=_file)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            print 'Errore upload: ', url, 'Codice Errore: ', e
        else:
            event_timestamp = r.text
            print '98:CONTENUTO r.text:', r.text
            return event_timestamp
        return False

    def do_modify(self, data):
        filepath = os.path.join(self.cfg['sharing_path'], data['filepath'])
        url = ''.join([self.files_url, data['filepath']])
        _file = {'file': (open(filepath, 'rb'))}
        print 'do_modify', url
        try:
            r = requests.put(url, auth=self.auth, files=_file)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            print 'Errore MODIFY: ', url, 'Codice Errore: ', e
        else:
            event_timestamp = r.text
            print '114:CONTENUTO r.text:', r.text
            return event_timestamp
        return False

    # actions:

    def do_move(self, data):
        url = ''.join([self.actions_url, 'move'])
        d = {'src': data['src'], 'dst': data['dst']}
        print 'do_move', url
        try:
            r = requests.post(url, auth=self.auth, data=d)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            print 'Errore MOVE: ', url, 'Codice Errore: ', e
        else:
            event_timestamp = r.text
            print '114:CONTENUTO r.text:', r.text
            return event_timestamp
        return False

    def do_delete(self, data):
        url = ''.join([self.actions_url, 'delete'])
        print 'do_delete', url
        d = {'filepath': data['filepath']}
        try:
            r = requests.post(url, auth=self.auth, data=d)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            print 'Errore DELETE: ', url, 'Codice Errore: ', e
        else:
            event_timestamp = r.text
            print '146:CONTENUTO r.text:', r.text
            return event_timestamp
        return False

    def do_copy(self, data):
        url = ''.join([self.actions_url, 'copy'])
        d = {'src': data['src'], 'dst': data['dst']}
        print 'do_copy', url
        try:
            r = requests.post(url, auth=self.auth, data=d)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            print 'Errore COPY: ', url, 'Codice Errore: ', e
        else:
            event_timestamp = r.text
            print '161:CONTENUTO r.text:', r.text
            return event_timestamp
        return False

    def do_get_server_snapshot(self, data):
        url = self.files_url
        print 'get_server_snapshot', url
        try:
            r = requests.get(url, auth=self.auth)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            print 'Errore GET_SERVER_SNAPSHOT: ', url, 'Codice Errore: ', e
            if 'UNAUTHORIZED' in e[0]:
                self.do_reguser(('pasquale', 'secretpass'))
                return self.do_get_server_snapshot(data)
        else:
            return json.loads(r.text)

    def _default(self, method):
        print 'Received Unknown Command:', method