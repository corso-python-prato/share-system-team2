#!/usr/bin/env python
#-*- coding: utf-8 -*-

__author__ = 'milly, eatsjobs'

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
import os


class ConnectionManager(object):

    def __init__(self, cfg):
        self.cfg = cfg        

    def dispatch_request(self, command, args):

        method_name = ''.join(['do_', command])
        return getattr(self, method_name, self._default)(args)

    def _send_request(self, api_method, resource, args):
        pass

    def do_reguser(self, param):
        
        data = {'username': param[0], 'password': param[1]}
        r = requests.post(''.join([self.cfg['server_address'], self.cfg['api_suffix'], 'signup']), data=data)

        print r.status_code

        # we will manages the response


    def do_upload(self, data):
        print 'do_upload'
        abspath = os.path.abspath(''.join(['sharing_folder/', data['filepath'] ]))
        d = {
            'file': (open(abspath,'rb')),
        }
        url = ''.join([self.cfg['server_address'], self.cfg['api_suffix'], 'files/', data['filepath']])
        r = requests.post(url, auth=(self.cfg['user'],self.cfg['pass']), files=d)
        print r.status_code


    def do_download(self, data):
        print 'do_download'
        url = ''.join([self.cfg['server_address'], self.cfg['api_suffix'], 'files/', data['filepath']])
        r = requests.get(url, auth=(self.cfg['user'],self.cfg['pass']))
        with open(os.path.join(self.cfg['sharing_path'],data['filepath']), 'wb') as f:
            f.write(r.content)
        return r.content

    def do_modify(self, data):
        print 'do_modify'
        abspath = os.path.abspath(''.join(['sharing_folder/', data['filepath'] ]))
        d = {
            'file': (open(abspath,'rb')),
        }
        url = ''.join([self.cfg['server_address'], self.cfg['api_suffix'], 'files/', data['filepath']])
        r = requests.put(url, auth=(self.cfg['user'],self.cfg['pass']), files=d)
        print r.status_code                

    #actions:
    def do_move(self, data):
        print 'do_move'
        url = ''.join([self.cfg['server_address'],self.cfg['api_suffix'],'move'])        
        d = {'src_path':data['src_path'], 'dest_path':data['dest_path']}
        r = requests.post(url, auth=(self.cfg['user'],self.cfg['pass']), data=json.dumps(d))
        print r.status_code

    def do_delete(self, data):
        print 'do_move'
        url = ''.join([self.cfg['server_address'],self.cfg['api_suffix'], 'actions/delete'])
        r = requests.post(url, auth=(self.cfg['user'],self.cfg['pass']), data=data )
        print r

    def do_copy(self, data):
        print data

    def do_get_server_state(self, data):
        url = ''.join([self.cfg['server_address'],self.cfg['api_suffix'],'files'])
        r = requests.get(url, auth=(self.cfg['user'],self.cfg['pass']))
        return json.loads(r.content)

    def _default(self, data):
        print 'Unknown Command'

    #shares: