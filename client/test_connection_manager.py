#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import connection_manager
import os
import json
import httpretty
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

        if os.path.isfile(TestConnectionManager.CONFIG_FILEPATH):
            with open(TestConnectionManager.CONFIG_FILEPATH, 'r') as fo:
                config = json.load(fo)
            if config:
                self.cfg = config
                self.test_url = ''.join((self.cfg['server_address'], self.cfg['api_suffix']))
                self.cm = connection_manager.ConnectionManager(self.cfg)
            else:
                print "Impossible to load cfg file"

    def tearDown(self):
        httpretty.disable()
        httpretty.reset()

    # files:
    @httpretty.activate
    def test_download_normal_file(self):
        httpretty.register_uri(httpretty.GET, ''.join((self.test_url, 'files/file.txt')), status=201)
        data = {'filepath': 'file.txt'}
        response = self.cm.do_download(data)
        self.assertEqual(response, 201)

    def test_download_unexistent_file(self):
        print "53:questa e' self.test_url:", self.test_url
        print ''.join((self.test_url, 'files/not_exist.txt'))
        httpretty.register_uri(httpretty.GET, ''.join((self.test_url, 'files/not_exist.txt')), status=404)
        data = {'filepath': 'not_exist.txt'}
        response = self.cm.do_download(data)
        self.assertEqual(response, False)

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