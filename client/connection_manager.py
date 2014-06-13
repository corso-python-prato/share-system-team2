#!/usr/bin/env python
#-*- coding: utf-8 -*-

__author__ = 'milly'

# API:
#  - GET /diffs, con parametro timestamp
#
# files:
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
#


import requests
import json


class ConnectionManager(object):

    def __init__(self, cfg):
        self.cfg = cfg        

    def dispatch_request(self, command, args):

        method_name = 'do_' + command
        getattr(self, method_name, self._default)(args)

    def _send_request(self, api_method, resource, args):
        pass

    def do_reguser(self, param):
        
        data = {'username': self.cfg['user'], 'password': self.cfg['password']}
        r = requests.post(self.cfg['server_address'] + self.cfg['api_suffix'], data=data)

        print r.status_code

        # we will manages the response


    def do_copy(self, data):
        print data        

    def do_upload(self, data):
        print data        

    def do_download(self, data):
        print data        

    def do_modify(self, data):
        print data        

    def do_move(self, data):
        print data

    def do_delete(self, data):
        print data

    def _default(self, data):
        print 'Unknown Command'