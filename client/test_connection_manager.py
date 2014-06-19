#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import connection_manager

import requests
import httpretty
import json
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
    def setUp(self):
        config = {'sharing_path': './sharing_folder',
                  'host': 'localhost',
                  'port': 50001,
                  'api_suffix': '/API/V1/',
                  'server_address': 'http://www.pyboxtest.com',
                  'user': 'pasquale',
                  'pass': 'secretpass',
                  }

        # httpretty.register_uri(httpretty.GET, 'http://fake.com:5000/API/V1/files/foo.txt', status=201)
        # httpretty.register_uri(httpretty.GET, 'http://fake.com:5000/API/V1/files/not_exist.txt', status=404)
        # httpretty.register_uri(httpretty.POST, 'http://fake.com/API/V1/signup', status=201)
        self.cm = connection_manager.ConnectionManager(config)

    # files:
    @httpretty.activate
    def test_do_download(self):
        httpretty.register_uri(httpretty.GET, 'http://www.pyboxtest.com/API/V1/files/foo.txt', status=200)
        httpretty.register_uri(httpretty.GET, 'http://www.pyboxtest.com/API/V1/files/not_authenticated', status=401)

        data = {'filepath': 'foo.txt'}
        response = self.cm.do_download(data)

        self.assertEqual(response, 200)

    @httpretty.activate
    def test_do_upload(self):
        httpretty.register_uri(httpretty.POST, 'http://www.pyboxtest.com/API/V1/files/foo.txt', status=200)
        response = self.cm.do_upload({'filepath': 'foo.txt'})

        self.assertEqual(response, 200)

    @httpretty.activate
    def test_do_modify(self):
        httpretty.register_uri(httpretty.PUT, 'http://www.pyboxtest.com/API/V1/files/foo.txt', status=201)

        response = self.cm.do_modify({'filepath': 'foo.txt'})

        self.assertEqual(response, 201)

    # actions:
    @httpretty.activate
    def test_do_move(self):
        httpretty.register_uri(httpretty.POST, 'hhttp://www.pyboxtest.com/API/V1/actions/foo.txt', status=201)

        response = self.cm.do_move({'src_path': 'foo.txt', 'dest_path': 'folder/foo.txt'})

        self.assertEqual(response, 200)

    @httpretty.activate
    def test_do_delete(self):
        httpretty.register_uri(httpretty.POST, 'http://www.pyboxtest.com/API/V1/actions/foo.txt', status=200)

        response = self.cm.do_delete({'filepath': 'foo.txt'})

        self.assertEqual(response, 200)


if __name__ == '__main__':
    unittest.main()
