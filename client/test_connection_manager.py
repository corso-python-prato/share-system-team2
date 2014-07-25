#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from connection_manager import ConnectionManager
import os
import json
import httpretty
import time
import shutil
# API:
# - GET /diffs, con parametro timestamp
#
# files:
# - GET /files/<path> - scarica un file
# - POST /files/<path> - crea un file
# - PUT /files/<path> - modifica un file
# actions:
#  - POST /actions/copy - parametri src, dest
#  - POST /actions/delete - parametro path
#  - POST /actions/move - parametri src, dest
# ---------
# shares:
#  - POST /shares/<root_path>/<user> - crea (se necessario) lo share, e l’utente che “vede” la condivisione
#  - DELETE /shares/<root_path> - elimina del tutto lo share
#  - DELETE /shares/<root_path>/<user> - elimina l’utente dallo share

# Test-user account details
USR, PW = 'client_user@mail.com', 'Mail_85'

class TestConnectionManager(unittest.TestCase):
    CONFIG_DIR = os.path.join(os.environ['HOME'], '.PyBox')
    CONFIG_FILEPATH = os.path.join(CONFIG_DIR, 'daemon_config')
    LOCAL_DIR_STATE_PATH = os.path.join(CONFIG_DIR, 'dir_state')

    def setUp(self):
        httpretty.enable()

        with open(TestConnectionManager.CONFIG_FILEPATH, 'r') as fo:
            self.cfg = json.load(fo)

        self.auth = (self.cfg['user'], self.cfg['pass'])
        # override
        self.cfg['server_address'] = "http://www.pyboxtest.com"
        self.cfg['sharing_path'] = os.path.join(os.getcwd(), "sharing_folder")

        # create this auth testing
        self.authServerAddress = "http://" + self.cfg['user'] + ":" + self.cfg['pass'] + "@www.pyboxtest.com"
        # example of self.base_url = 'http://localhost:5000/API/V1/'
        self.base_url = ''.join([self.cfg['server_address'], self.cfg['api_suffix']])
        self.files_url = ''.join([self.base_url, 'files/'])
        self.actions_url = ''.join([self.base_url, 'actions/'])
        self.shares_url = ''.join([self.base_url, 'shares/'])
        self.user_url = ''.join([self.base_url, 'users/'])

        self.cm = ConnectionManager(self.cfg)
        self.make_fake_dir()

    @httpretty.activate
    def test_register_user(self):
        """
        Test register user api:
        method = POST
        resource = <user>
        data = password=<password>
        """
        data = (USR, PW)
        url = ''.join((self.user_url, USR))
        content = 'user activated'
        content_jsoned = json.dumps(content)
        httpretty.register_uri(httpretty.POST, url, status=200, body= content_jsoned)
        response = self.cm.do_register(data)
        self.assertIn('content', response)
        self.assertEqual(response['content'], content)

    @httpretty.activate
    def test_register_user_with_weak_password(self):
        """
        Test register user api with weak password:
        method = POST
        resource = <user>
        data = password=<password>
        """
        weak_password = 'Password'
        data = (USR, weak_password)
        url = ''.join((self.user_url, USR))
        content = {'type_of_improvement': 'improvement suggested'}
        content_jsoned = json.dumps(content)
        httpretty.register_uri(httpretty.POST, url, status=403, body=content_jsoned)
        response = self.cm.do_register(data)
        self.assertIn('improvements', response)
        self.assertEqual(response['improvements'], content)

    @httpretty.activate
    def test_register_user_with_already_existent_user(self):
        """
        Test register user api with already existent user:
        method = POST
        resource = <user>
        data = password=<password>
        """
        data = (USR, PW)
        url = ''.join((self.user_url, USR))
        # This is the only case where server doesn't send data with the message error
        httpretty.register_uri(httpretty.POST, url, status=409)
        response = self.cm.do_register(data)
        response = self.cm.do_register(data)
        self.assertIn('content', response)
        self.assertIsInstance(response['content'], str)

    @httpretty.activate
    def test_activate_user(self):
        """
        Test activate user api:
        method = PUT
        resource = <user>
        data = activation_code=<token>
        """
        user = 'mail@mail.it'
        token = '6c9fb345c317ad1d31ab9d6445d1a820'
        data = (user, token)
        url = ''.join((self.user_url, user))

        httpretty.register_uri(httpretty.PUT, url, status=201, body='user activated')
        response = self.cm.do_activate(data)
        self.assertNotEqual(response, False)
        self.assertIsInstance(response, unicode)

        httpretty.register_uri(httpretty.PUT, url, status=404)
        self.assertFalse(self.cm.do_activate(data))

        httpretty.register_uri(httpretty.PUT, url, status=409)
        self.assertFalse(self.cm.do_activate(data))

    @httpretty.activate
    def test_post_recover_password_not_found(self):
        """
        Test that if /users/<email>/reset POST == 404 then cm return None
        """
        # An unknown user (neither registered nor pending) is a resource not found for the server...
        email = 'utentesconosciuto@gmail.com'
        url = self.user_url + email + '/reset'
        # ...so the server should return a 404:
        httpretty.register_uri(httpretty.POST, url, status=404)
        # and the command manager must return None in this case
        response = self.cm.do_reqrecoverpass(email)
        self.assertIsNone(response)

    @httpretty.activate
    def test_post_recover_password_accept(self):
        """
        Test that if /users/<email>/reset POST == 202 then cm return True
        """
        email = 'pippo@gmail.com'
        url = self.user_url + email + '/reset'
        httpretty.register_uri(httpretty.POST, url, status=202)
        response = self.cm.do_reqrecoverpass(email)
        self.assertTrue(response)

    @httpretty.activate
    def test_put_recover_password_not_found(self):
        """
        Test that if /users/<email> PUT == 404 then cm return None
        """
        email = 'pippo@gmail.com'
        recoverpass_code = os.urandom(16).encode('hex')
        new_password = 'mynewpass'
        url = self.user_url + email
        httpretty.register_uri(httpretty.PUT, url, status=404)
        data = email, recoverpass_code, new_password
        response = self.cm.do_recoverpass(data)
        self.assertFalse(response)

    @httpretty.activate
    def test_put_recover_password_ok(self):
        """
        Test that if /users/<email> PUT == 200 then cm return True
        """
        email = 'pippo@gmail.com'
        recoverpass_code = os.urandom(16).encode('hex')
        new_password = 'mynewpass'
        url = self.user_url + email
        httpretty.register_uri(httpretty.PUT, url, status=200)
        data = email, recoverpass_code, new_password
        response = self.cm.do_recoverpass(data)
        self.assertTrue(response)

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

        # prepare fake server
        url = ''.join((self.files_url, 'foo.txt'))
        js = json.dumps({"server_timestamp": time.time()})
        recv_js = json.loads(js)
        httpretty.register_uri(httpretty.POST, url, status=201,
                               body=js,
                               content_type="application/json")

        # call api
        response = self.cm.do_upload({'filepath': 'foo.txt', 'md5': 'test_md5'})
        self.assertEqual(response, recv_js)

    # actions:
    @httpretty.activate
    def test_do_move(self):
        url = ''.join((self.actions_url, 'move'))
        js = json.dumps({"server_timestamp": time.time()})
        recv_js = json.loads(js)
        httpretty.register_uri(httpretty.POST, url, status=201,
                               body=js,
                               content_type="application/json")

        response = self.cm.do_move({'src': 'foo.txt', 'dst': 'folder/foo.txt'})
        self.assertEqual(response, recv_js)

    @httpretty.activate
    def test_do_delete(self):
        url = ''.join((self.actions_url, 'delete'))

        js = json.dumps({"server_timestamp": time.time()})
        recv_js = json.loads(js)
        httpretty.register_uri(httpretty.POST, url, status=201,
                               body=js,
                               content_type="application/json")
        d = {'filepath': 'foo.txt'}

        response = self.cm.do_delete(d)
        self.assertEqual(response, recv_js)

    @httpretty.activate
    def test_do_modify(self):
        url = ''.join((self.files_url, 'foo.txt'))
        js = json.dumps({"server_timestamp": time.time()})
        recv_js = json.loads(js)
        httpretty.register_uri(httpretty.PUT, url, status=201,
                               body=js,
                               content_type="application/json")

        response = self.cm.do_modify({'filepath': 'foo.txt', 'md5': 'test_md5'})
        self.assertEqual(response, recv_js)

    @httpretty.activate
    def test_do_copy(self):
        url = ''.join([self.actions_url, 'copy'])
        d = {'src': 'foo.txt', 'dst': 'folder/foo.txt'}
        js = json.dumps({"server_timestamp": time.time()})
        recv_js = json.loads(js)
        httpretty.register_uri(httpretty.POST, url, status=201,
                               body=js,
                               content_type="application/json")

        response = self.cm.do_copy(d)
        self.assertEqual(response, recv_js)

    @httpretty.activate
    def test_get_server_snapshot(self):
        url = self.files_url
        js = json.dumps({'files': 'foo.txt'})

        httpretty.register_uri(httpretty.GET, url, status=201,
                               body=js,
                               content_type="application/json")

        response = self.cm.do_get_server_snapshot('')
        self.assertEqual(json.dumps(response), js)

    def tearDown(self):
        httpretty.disable()
        httpretty.reset()
        self.remove_fake_dir()

    def make_fake_dir(self):
        sharing_path = os.path.join(self.cfg['sharing_path'])

        if os.path.exists(sharing_path):
            shutil.rmtree(sharing_path)
        else:
            os.makedirs(os.path.join(self.cfg['sharing_path']))

        fake_file = os.path.join(self.cfg['sharing_path'], 'foo.txt')
        with open(fake_file, 'w') as fc:
            fc.write('foo.txt :)')

    def remove_fake_dir(self):
        shutil.rmtree(os.path.join(self.cfg['sharing_path']))


if __name__ == '__main__':
    unittest.main()
