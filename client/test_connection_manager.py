#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from connection_manager import ConnectionManager
import os
import json
import httpretty
import time
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


class TestConnectionManager(unittest.TestCase):
    CONFIG_DIR = os.path.join(os.environ['HOME'], '.PyBox')
    CONFIG_FILEPATH = os.path.join(CONFIG_DIR, 'daemon_config')
    LOCAL_DIR_STATE_PATH = os.path.join(CONFIG_DIR,'dir_state')

    def setUp(self):        
        httpretty.enable() 
        #self.cm = ConnectionManager()
        with open(TestConnectionManager.CONFIG_FILEPATH,'r') as fo:
            self.cfg = json.load(fo)

        self.auth = (self.cfg['user'], self.cfg['pass'])
        self.cfg['server_address'] = "http://www.pyboxtest.com"

        # create this auth testing
        self.authServerAddress = "http://"+self.cfg['user']+":"+self.cfg['pass']+"@www.pyboxtest.com"        
        # example of self.base_url = 'http://localhost:5000/API/V1/'
        self.base_url = ''.join([self.cfg['server_address'], self.cfg['api_suffix']])
        self.files_url = ''.join([self.base_url, 'files/'])
        self.actions_url = ''.join([self.base_url, 'actions/'])
        self.shares_url = ''.join([self.base_url, 'shares/'])

        self.cm = ConnectionManager(self.cfg)

    # files:
    @httpretty.activate
    def test_download_normal_file(self):
        url = ''.join((self.files_url, 'file.txt'))
        
        httpretty.register_uri(httpretty.GET, url, status=201)
        data = {'filepath': 'file.txt'}
        response = self.cm.do_download(data)        
        self.assertEqual(response, True)

    @httpretty.activate
    def test_download_file_not_exists(self):
        url = ''.join((self.files_url, 'file.tx'))
        
        httpretty.register_uri(httpretty.GET, url, status=404)
        data = {'filepath': 'file.tx'}
        response = self.cm.do_download(data)        
        self.assertEqual(response, False)

    @httpretty.activate
    def test_do_upload_success(self):
        # make fake file
        fake_file = os.path.join(self.cfg['sharing_path'],'foo.txt')
        with open(fake_file,'w') as fc:
            fc.write('foo.txt :)')

        # prepare fake server
        url = ''.join((self.files_url, 'foo.txt'))        
        js = json.dumps({"server_timestamp":time.time()})
        httpretty.register_uri(httpretty.POST, url, status=201, 
                                                    body=js,
                                                    content_type="application/json")

        # call api
        response = self.cm.do_upload({'filepath':'foo.txt'})        
        os.remove(fake_file)
        self.assertEqual(response, js)

    # actions:
    @httpretty.activate
    def test_do_move(self):
        url = ''.join((self.actions_url, 'move'))
        
        js = json.dumps({"server_timestamp":time.time()})
        httpretty.register_uri(httpretty.POST, url, status=201, 
            body=js,
            content_type="application/json")

        response = self.cm.do_move({'src': 'foo.txt', 'dst': 'folder/foo.txt'})        
        self.assertEqual(response, js)

    def tearDown(self):
        httpretty.disable()
        httpretty.reset()

if __name__ == '__main__':
    unittest.main()

    # def test_download_unexistent_file(self):
    #     print "53:questa e' self.test_url:", self.test_url
    #     print ''.join((self.test_url, 'files/not_exist.txt'))
    #     httpretty.register_uri(httpretty.GET, ''.join((self.test_url, 'files/not_exist.txt')), status=404)
    #     data = {'filepath': 'not_exist.txt'}
    #     response = self.cm.do_download(data)
    #     self.assertEqual(response, False)

    # @httpretty.activate
    # def test_do_upload(self):
    #     httpretty.register_uri(httpretty.POST, 'http://www.pyboxtest.com/API/V1/files/foo.txt', status=200)
    #     response = self.cm.do_upload({'filepath': 'foo.txt'})
    #
    #     self.assertEqual(response, 200)
    #
    # @httpretty.activate
    # def test_do_modify(self):
    #     httpretty.register_uri(httpretty.PUT, 'http://www.pyboxtest.com/API/V1/files/foo.txt', status=201)
    #
    #     response = self.cm.do_modify({'filepath': 'foo.txt'})
    #
    #     self.assertEqual(response, 201)
    #
    # # actions:
    # @httpretty.activate
    # def test_do_move(self):
    #     httpretty.register_uri(httpretty.POST, 'hhttp://www.pyboxtest.com/API/V1/actions/foo.txt', status=201)
    #
    #     response = self.cm.do_move({'src_path': 'foo.txt', 'dest_path': 'folder/foo.txt'})
    #
    #     self.assertEqual(response, 200)
    #
    # @httpretty.activate
    # def test_do_delete(self):
    #     httpretty.register_uri(httpretty.POST, 'http://www.pyboxtest.com/API/V1/actions/foo.txt', status=200)
    #
    #     response = self.cm.do_delete({'filepath': 'foo.txt'})
    #
    #     self.assertEqual(response, 200)