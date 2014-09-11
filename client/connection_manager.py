#!/usr/bin/env python
# -*- coding: utf-8 -*-

# API:
#
# files:
# - GET /files/ - ottiene la lista dei file sul server con relativi metadati necessari e/o md5
# - GET /files/<path> - scarica un file
# - POST /files/<path> - crea un file
# - PUT /files/<path> - modifica un file
# actions:
# - POST /actions/copy - parametri src, dest
# - POST /actions/delete - parametro path
# - POST /actions/move - parametri src, dest
# ---------
# shares:
# - POST /shares/<root_path>/<user> - crea (se necessario) lo share, e l’utente che “vede” la condivisione
# - DELETE /shares/<root_path> - elimina del tutto lo share
# - DELETE /shares/<root_path>/<user> - elimina l’utente dallo share

import requests
from urllib import quote as urlquote
import json
import os
import logging


class ConnectionManager(object):
    # This is the char filter for url encoder, this list of char aren't translated in percent style
    ENCODER_FILTER = '+/: '

    EXCEPTIONS_CATCHED = (requests.HTTPError,
                          requests.exceptions.ConnectionError,
                          requests.exceptions.MissingSchema,
                        )

    def __init__(self, cfg, logging_level=logging.ERROR):
        self.load_cfg(cfg)

        self.logger = logging.getLogger("ConMng")
        self.logger.setLevel(level=logging_level)

        # create a file handler
        if not os.path.isdir('log'):
            os.makedirs('log')

        handler = logging.FileHandler('log/test_connection_manager.log')
        handler.setLevel(logging_level)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging_level)

        console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)

        self.logger.addHandler(console_handler)

    def load_cfg(self, cfg):
        """
        Load the configuration received from client_daemon
        :param cfg: Dictionary where is contained the configuration
        """
        self.cfg = cfg
        self.auth = (self.cfg.get('user', None), self.cfg.get('pass', None))

        # example of self.base_url = 'http://localhost:5000/API/V1/'
        self.base_url = ''.join([self.cfg['server_address'], self.cfg['api_suffix']])
        self.files_url = ''.join([self.base_url, 'files/'])
        self.actions_url = ''.join([self.base_url, 'actions/'])
        self.shares_url = ''.join([self.base_url, 'shares/'])
        self.users_url = ''.join([self.base_url, 'users/'])

    def dispatch_request(self, command, args=None):
        method_name = ''.join(['do_', command])
        try:
            return getattr(self, method_name)(args)
        except AttributeError:
            self._default(method_name)

    def do_login(self, data):
        url = self.files_url
        user = data[0]
        password = data[1]
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_login', url, data))
        try:
            r = requests.get(url, auth=(user, password))
            r.raise_for_status()
            return {'content': 'User authenticated', 'successful': True}
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('{}: URL: {} - EXCEPTION_CATCHED: {} '.format('do_login', url, e))
            return {'content': 'Impossible to login, user unauthorized.', 'successful': False}

    def do_register(self, data):
        """
        Send registration user request
        """
        req = {'password': data[1]}
        url = ''.join([self.users_url, data[0]])
        self.logger.info('do_register: URL: {} - DATA: {} '.format(url, data))

        try:
            r = requests.post(urlquote(url, '+/: '), data=req)
            # i must check before raise_for_status to not destroy response
            if r.status_code == 403:
                return {'improvements': json.loads(r.text), 'successful': False}
            elif r.status_code == 409:
                return {'content': 'Error! User already existent!', 'successful': False}
            r.raise_for_status()
            return {'content': r.json(), 'successful': True}
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('do_register: URL: {} - EXCEPTION_CATCHED: {} '.format(url, e))
            return {'content': 'Error during registration:\n{}'.format(e), 'successful': False}

    def do_activate(self, data):
        """
        Send activation user request
        """
        req = {'activation_code': data[1]}
        url = ''.join([self.users_url, data[0]])
        self.logger.info('do_activate: URL: {} - DATA: {} '.format(url, data))

        try:
            r = requests.put(urlquote(url, '+/: '), data=req)
            if r.status_code == 404:
                return {'content': 'Error! Impossible to activate user! Unexistent user!', 'successful': False}
            elif r.status_code == 409:
                return {'content': 'Error! Impossible to activate user! User already activated!', 'successful': False}
            r.raise_for_status()
            return {'content': r.json(), 'successful': True}
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('do_activate: URL: {} - EXCEPTION_CATCHED: {} '.format(url, e))
            return {'content': 'Error during activation:\n{}'.format(e), 'successful': False}

    def do_reqrecoverpass(self, data):
        """
        Ask server for reset current user password.
        """
        mail = data
        url = '{}{}/reset'.format(self.users_url, mail)
        try:
            r = requests.post(urlquote(url, '+/: '))
            r.raise_for_status()
            return r.text
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('do_reqrecoverpass: URL: {} - EXCEPTION_CATCHED: {}'.format(url, e))

    def do_recoverpass(self, data):
        """
        Change current password using the code given by email.
        """
        mail, recoverpass_code, new_password = data
        url = '{}{}'.format(self.users_url, mail)
        try:
            r = requests.put(urlquote(url, '+/: '),
                             data={'password': new_password,
                                   'recoverpass_code': recoverpass_code})
            r.raise_for_status()
            return r.text
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('do_recoverpass: URL: {} - EXCEPTION_CATCHED: {}'.format(url, e))

    # files

    def do_download(self, data):
        url = ''.join([self.files_url, data['filepath']])
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_download', url, data))
        try:
            r = requests.get(urlquote(url, '+/: '), auth=self.auth)
            r.raise_for_status()
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('{}: URL: {} - EXCEPTION_CATCHED: {} '.format('do_download', url, e))
            return {'content': 'Failed to download file from server.\n'
                               'Path: {}\nError: {}'.format(data['filepath'], e),
                    'successful': False}
        filepath = os.path.join(self.cfg['sharing_path'], data['filepath'])
        dirpath, filename = os.path.split(filepath)
        # Create all missing directories
        if not os.path.isdir(dirpath):
            os.makedirs(dirpath)
        if not os.path.exists(filepath):
            with open(filepath, 'wb') as f:
                f.write(r.content)
                return {'successful': True}
        else:
            return {'content': 'Warning! Download of file already existent! Operation Aborted.', 'successful': False}

    def do_upload(self, data):
        filepath = os.path.join(self.cfg['sharing_path'], data['filepath'])
        url = ''.join([self.files_url, data['filepath']])
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_upload', url, data))
        _file = {'file': (open(filepath, 'rb'))}
        try:
            r = requests.post(urlquote(url, '+/: '), auth=self.auth, files=_file, data={'md5': data['md5']})
            r.raise_for_status()
            return {'content': r.json(), 'successful': True}
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('{}: URL: {} - EXCEPTION_CATCHED: {} '.format('do_upload', url, e))
            return {'content': 'Failed to upload file to the server.\n'
                               'Path: {}\nError: {}'.format(data['filepath'], e),
                    'successful': False}

    def do_modify(self, data):
        filepath = os.path.join(self.cfg['sharing_path'], data['filepath'])
        url = ''.join([self.files_url, data['filepath']])
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_modify', url, data))
        _file = {'file': (open(filepath, 'rb'))}
        try:
            r = requests.put(urlquote(url, '+/: '), auth=self.auth, files=_file, data={'md5': data['md5']})
            r.raise_for_status()
            return {'content': r.json(), 'successful': True}
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('{}: URL: {} - EXCEPTION_CATCHED: {} '.format('do_modify', url, e))
            return {'content': 'Failed to modify file on server.\n'
                               'Path: {}\nError: {}'.format(data['filepath'], e),
                    'successful': False}

    # actions:

    def do_move(self, data):
        url = ''.join([self.actions_url, 'move'])
        d = {'src': data['src'], 'dst': data['dst']}
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_move', url, data))
        try:
            r = requests.post(urlquote(url, '+/: '), auth=self.auth, data=d)
            r.raise_for_status()
            return {'content': r.json(), 'successful': True}
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('{}: URL: {} - EXCEPTION_CATCHED: {} '.format('do_move', url, e))
            return {'content': 'Failed to move file on server.\n'
                               'Src path: {}\nDest Path: {}\nError: {}'.format(data['src'], data['dst'], e),
                    'successful': False}

    def do_delete(self, data):
        url = ''.join([self.actions_url, 'delete'])
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_delete', url, data))
        d = {'filepath': data['filepath']}
        try:
            r = requests.post(urlquote(url, '+/: '), auth=self.auth, data=d)
            r.raise_for_status()
            return {'content': r.json(), 'successful': True}
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('{}: URL: {} - EXCEPTION_CATCHED: {} '.format('do_delete', url, e))
            return {'content': 'Failed to delete file on server.\n'
                               'Path: {}\nError: {}'.format(data['filepath'], e),
                    'successful': False}

    def do_copy(self, data):
        url = ''.join([self.actions_url, 'copy'])
        d = {'src': data['src'], 'dst': data['dst']}
        self.logger.info('{}: URL: {} - DATA: {} '.format('do_copy', url, data))
        try:
            r = requests.post(urlquote(url, '+/: '), auth=self.auth, data=d)
            r.raise_for_status()
            return {'content': r.json(), 'successful': True}
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('{}: URL: {} - EXCEPTION_CATCHED: {} '.format('do_copy', url, e))
            return {'content': 'Failed to copy file on server.\n'
                               'Src path: {}\nDest Path: {}\nError: {}'.format(data['src'], data['dst'], e),
                    'successful': False}

    def do_get_server_snapshot(self, data):
        url = self.files_url

        self.logger.info('{}: URL: {} - DATA: {} '.format('do_get_server_snapshot', url, data))

        try:
            r = requests.get(urlquote(url, '+/: '), auth=self.auth)
            r.raise_for_status()
            return {'content': r.json(), 'successful': True}
        except ConnectionManager.EXCEPTIONS_CATCHED as e:
            self.logger.error('{}: URL: {} - EXCEPTION_CATCHED: {} '.format('do_get_server_snapshot', url, e))
            return {'content': 'Failed to get server snapshot, maybe server down?\nError: {}'.format(e), 'successful': False}

    def _default(self, method):
        print 'Received Unknown Command:', method
