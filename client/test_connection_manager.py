#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from connection_manager import ConnectionManager
import os
import json
import httpretty
import time
import shutil
import urllib

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

TEST_DIR = os.path.join(os.environ['HOME'], 'daemon_test')
CONFIG_DIR = os.path.join(TEST_DIR, '.PyBox')
CONFIG_FILEPATH = os.path.join(CONFIG_DIR, 'daemon_config')
LOCAL_DIR_STATE_FOR_TEST = os.path.join(CONFIG_DIR, 'local_dir_state')
TEST_SHARING_FOLDER = os.path.join(TEST_DIR, 'test_sharing_folder')
TEST_SERVER_ADDRESS = 'http://www.pyboxtest.com'

TEST_CFG = {
    'local_dir_state_path': LOCAL_DIR_STATE_FOR_TEST,
    'sharing_path': TEST_SHARING_FOLDER,
    'cmd_address': 'localhost',
    'cmd_port': 60001,
    'api_suffix': '/API/V1/',
    # no server_address to be sure
    'server_address': TEST_SERVER_ADDRESS,
    'user': 'user',
    'pass': 'pass',
    'activate': True
}


def create_environment():
    if not os.path.exists(TEST_DIR):
        os.makedirs(CONFIG_DIR)

    with open(CONFIG_FILEPATH, 'w') as f:
            json.dump(TEST_CFG, f, skipkeys=True, ensure_ascii=True, indent=4)

# Test-user account details
USR, PW = 'client_user@mail.com', 'Mail_85'


def make_fake_dir():
    if os.path.exists(TEST_SHARING_FOLDER):
        shutil.rmtree(TEST_SHARING_FOLDER)
    os.makedirs(TEST_SHARING_FOLDER)

    fake_file = os.path.join(TEST_SHARING_FOLDER, 'foo.txt')
    with open(fake_file, 'w') as f:
        f.write('foo.txt :)')


def remove_fake_dir():
    shutil.rmtree(TEST_SHARING_FOLDER)


class TestConnectionManager(unittest.TestCase):

    def setUp(self):
        httpretty.enable()
        create_environment()
        make_fake_dir()
        with open(CONFIG_FILEPATH, 'r') as fo:
            self.cfg = json.load(fo)

        self.auth = (self.cfg['user'], self.cfg['pass'])
        self.base_url = ''.join([self.cfg['server_address'], self.cfg['api_suffix']])
        self.files_url = ''.join([self.base_url, 'files/'])
        self.actions_url = ''.join([self.base_url, 'actions/'])
        self.shares_url = ''.join([self.base_url, 'shares/'])
        self.user_url = ''.join([self.base_url, 'users/'])

        self.cm = ConnectionManager(self.cfg)

    def tearDown(self):
        httpretty.disable()
        httpretty.reset()
        remove_fake_dir()

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
        content = 'user created'
        content_jsoned = json.dumps(content)
        httpretty.register_uri(httpretty.POST, url, status=200, body=content_jsoned)
        response = self.cm.do_register(data)
        self.assertIn('content', response)
        self.assertEqual(response['content'], content)
        self.assertTrue(response['successful'])

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
        self.assertFalse(response['successful'])

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
        self.assertIn('content', response)
        self.assertIsInstance(response['content'], str)
        self.assertFalse(response['successful'])

    @httpretty.activate
    def test_fail_to_register_user(self):
        """
        Test failed register request
        Test activate user api:
        method = POST
        resource = <user>
        data = password=<password>
        """
        data = (USR, PW)
        url = ''.join((self.user_url, USR))
        httpretty.register_uri(httpretty.POST, url, status=500)

        response = self.cm.do_register(data)
        self.assertIsInstance(response['content'], str)
        self.assertFalse(response['successful'])

    @httpretty.activate
    def test_activate_user(self):
        """
        Test successful activation
        Test activate user api:
        method = PUT
        resource = <user>
        data = activation_code=<token>
        """
        user = 'mail@mail.it'
        token = '6c9fb345c317ad1d31ab9d6445d1a820'
        data = (user, token)
        url = ''.join((self.user_url, user))
        answer = 'user activated'
        answer_jsoned = json.dumps(answer)
        httpretty.register_uri(httpretty.PUT, url, status=201, body=answer_jsoned)

        response = self.cm.do_activate(data)
        self.assertIsInstance(response['content'], unicode)
        self.assertTrue(response['successful'])

    @httpretty.activate
    def test_activate_user_already_existent(self):
        """
        Test activate user already existent
        Test activate user api:
        method = PUT
        resource = <user>
        data = activation_code=<token>
        """
        user = 'mail@mail.it'
        token = 'bad_token'
        data = (user, token)
        url = ''.join((self.user_url, user))
        httpretty.register_uri(httpretty.PUT, url, status=409)

        response = self.cm.do_activate(data)
        self.assertIsInstance(response['content'], str)
        self.assertFalse(response['successful'])

    @httpretty.activate
    def test_activate_user_not_existent(self):
        """
        Test activate user not existent
        Test activate user api:
        method = PUT
        resource = <user>
        data = activation_code=<token>
        """
        user = 'mail@mail.it'
        token = 'bad_token'
        data = (user, token)
        url = ''.join((self.user_url, user))
        httpretty.register_uri(httpretty.PUT, url, status=404)

        response = self.cm.do_activate(data)
        self.assertIsInstance(response['content'], str)
        self.assertFalse(response['successful'])

    @httpretty.activate
    def test_fail_to_activate_user(self):
        """
        Test failed activation request
        Test activate user api:
        method = PUT
        resource = <user>
        data = activation_code=<token>
        """
        user = 'mail@mail.it'
        token = 'bad_token'
        data = (user, token)
        url = ''.join((self.user_url, user))
        httpretty.register_uri(httpretty.PUT, url, status=500)

        response = self.cm.do_activate(data)
        self.assertIsInstance(response['content'], str)
        self.assertFalse(response['successful'])

    @httpretty.activate
    def test_login_user(self):
        """
        Test login user api:
        method = get
        resource = <user>
        data = password=<password>
        """
        data = (USR, PW)
        url = self.files_url
        content = {'file1': 'foo.txt', 'file2': 'dir/foo.txt'}
        content_jsoned = json.dumps(content)
        httpretty.register_uri(httpretty.GET, url, status=200, body=content_jsoned)
        response = self.cm.do_login(data)
        self.assertIn('content', response)
        self.assertIsInstance(response['content'], str)
        self.assertTrue(response['successful'])

    @httpretty.activate
    def test_login_user_failed(self):
        """
        Test login user api with weak password:
        method = GET
        resource = <user>
        data = password=<password>
        """
        data = ('bad_user', 'bad_pass')
        url = self.files_url
        httpretty.register_uri(httpretty.GET, url, status=401)
        response = self.cm.do_login(data)
        self.assertIn('content', response)
        self.assertIsInstance(response['content'], str)
        self.assertFalse(response['successful'])

    @httpretty.activate
    def test_login_fail_connection(self):
        """
        Test login user api:
        method = get
        resource = <user>
        data = password=<password>
        """
        data = (USR, PW)
        url = self.files_url
        httpretty.register_uri(httpretty.GET, url, status=400)
        response = self.cm.do_login(data)
        self.assertIsInstance(response['content'], str)
        self.assertFalse(response['successful'])

    @httpretty.activate
    def test_post_recover_password_not_found(self):
        """
        Test that if /users/<email>/reset POST == 404 then cm return None
        """
        # An unknown user (neither registered nor pending) is a resource not found for the server...
        email = 'unknown.user@gmail.com'
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

    @httpretty.activate
    def test_addshare(self):
        """
        Test activate user api:
        method = PUT
        resource = <user>
        data = activation_code=<token>
        """
        user = 'mail@mail.it'
        shared_folder = 'folder'
        data = (shared_folder, user)
        url = ''.join([self.shares_url, shared_folder, '/', user])

        httpretty.register_uri(httpretty.POST, url, status=200, body='added shared folder')
        response = self.cm.do_addshare(data)
        self.assertNotEqual(response, False)
        self.assertIsInstance(response, unicode)

        httpretty.register_uri(httpretty.POST, url, status=404)
        self.assertFalse(self.cm.do_addshare(data))

        httpretty.register_uri(httpretty.POST, url, status=409)
        self.assertFalse(self.cm.do_addshare(data))

    @httpretty.activate
    def test_removeshare(self):
        """
        Test activate user api:
        method = PUT
        resource = <user>
        data = activation_code=<token>
        """
        shared_folder = 'folder'
        data = (shared_folder, )
        url = ''.join([self.shares_url, shared_folder])

        httpretty.register_uri(httpretty.DELETE, url, status=200, body='share removed')
        response = self.cm.do_removeshare(data)
        self.assertNotEqual(response, False)
        self.assertIsInstance(response, unicode)

        httpretty.register_uri(httpretty.DELETE, url, status=404)
        self.assertFalse(self.cm.do_removeshare(data))

        httpretty.register_uri(httpretty.DELETE, url, status=409)
        self.assertFalse(self.cm.do_removeshare(data))

    @httpretty.activate
    def test_removeshareduser(self):
        """
        Test activate user api:
        method = PUT
        resource = <user>
        data = activation_code=<token>
        """
        user = 'mail@mail.it'
        shared_folder = 'folder'
        data = (shared_folder, user)
        url = ''.join([self.shares_url, shared_folder, '/', user])

        httpretty.register_uri(httpretty.DELETE, url, status=200, body='removed user from share')
        response = self.cm.do_removeshareduser(data)
        self.assertNotEqual(response, False)
        self.assertIsInstance(response, unicode)

        httpretty.register_uri(httpretty.DELETE, url, status=404)
        self.assertFalse(self.cm.do_removeshareduser(data))

        httpretty.register_uri(httpretty.DELETE, url, status=409)
        self.assertFalse(self.cm.do_removeshareduser(data))

    # files:
    @httpretty.activate
    def test_download_normal_file(self):
        url = ''.join((self.files_url, 'file.txt'))

        httpretty.register_uri(httpretty.GET, url, status=201)
        data = {'filepath': 'file.txt'}
        response = self.cm.do_download(data)
        self.assertEqual(response['successful'], True)

    @httpretty.activate
    def test_download_file_not_exists(self):
        url = ''.join((self.files_url, 'file.tx'))

        httpretty.register_uri(httpretty.GET, url, status=404)
        data = {'filepath': 'file.tx'}
        response = self.cm.do_download(data)
        self.assertEqual(response['successful'], False)
        self.assertIsInstance(response['content'], str)

    @httpretty.activate
    def test_do_upload_success(self):

        # prepare fake server
        url = ''.join((self.files_url, 'foo.txt'))
        msg = {'server_timestamp': time.time()}
        js = json.dumps(msg)
        httpretty.register_uri(httpretty.POST, url, status=201,
                               body=js,
                               content_type="application/json")

        # call api
        response = self.cm.do_upload({'filepath': 'foo.txt', 'md5': 'test_md5'})
        self.assertTrue(response['successful'])
        self.assertEqual(response['content'], msg)

    @httpretty.activate
    def test_do_upload_fail(self):

        # prepare fake server
        url = ''.join((self.files_url, 'foo.txt'))
        httpretty.register_uri(httpretty.POST, url, status=404,
                               content_type="application/json")

        # call api
        response = self.cm.do_upload({'filepath': 'foo.txt', 'md5': 'test_md5'})
        self.assertFalse(response['successful'])
        self.assertIsInstance(response['content'], str)

    @httpretty.activate
    def test_encode_of_url_with_strange_char(self):
        """
        Test the url encode of filename with strange char.
        I use upload method for example and i expect that httpretty answer at the right URL.
        """
        # Create the file with strange name
        strange_filename = 'name%with#strange~char'
        strange_filepath = os.path.join(TEST_SHARING_FOLDER, strange_filename)
        with open(strange_filepath, 'w') as f:
            f.write('file with strange name content')

        # prepare fake server
        encoded_filename = urllib.quote(strange_filename, self.cm.ENCODER_FILTER)
        url = ''.join((self.files_url, encoded_filename))
        print url
        msg = {'server_timestamp': time.time()}
        js = json.dumps(msg)
        httpretty.register_uri(httpretty.POST, url, status=201,
                               body=js,
                               content_type="application/json")

        # call api
        response = self.cm.do_upload({'filepath': strange_filename, 'md5': 'test_md5'})
        self.assertTrue(response['successful'])
        self.assertEqual(response['content'], msg)

    # actions:
    @httpretty.activate
    def test_do_move(self):
        url = ''.join((self.actions_url, 'move'))
        msg = {'server_timestamp': time.time()}
        js = json.dumps(msg)
        httpretty.register_uri(httpretty.POST, url, status=201,
                               body=js,
                               content_type="application/json")

        response = self.cm.do_move({'src': 'foo.txt', 'dst': 'folder/foo.txt'})
        self.assertTrue(response['successful'])
        self.assertEqual(response['content'], msg)

    @httpretty.activate
    def test_do_move_fail(self):
        url = ''.join((self.actions_url, 'move'))
        httpretty.register_uri(httpretty.POST, url, status=404,
                               content_type="application/json")

        response = self.cm.do_move({'src': 'foo.txt', 'dst': 'folder/foo.txt'})
        self.assertFalse(response['successful'])
        self.assertIsInstance(response['content'], str)

    @httpretty.activate
    def test_do_delete(self):
        url = ''.join((self.actions_url, 'delete'))
        msg = {'server_timestamp': time.time()}
        js = json.dumps(msg)
        httpretty.register_uri(httpretty.POST, url, status=201,
                               body=js,
                               content_type="application/json")
        d = {'filepath': 'foo.txt'}

        response = self.cm.do_delete(d)
        self.assertTrue(response['successful'])
        self.assertEqual(response['content'], msg)

    @httpretty.activate
    def test_do_delete_fail(self):
        url = ''.join((self.actions_url, 'delete'))
        httpretty.register_uri(httpretty.POST, url, status=404,
                               content_type="application/json")
        d = {'filepath': 'foo.txt'}

        response = self.cm.do_delete(d)
        self.assertFalse(response['successful'])
        self.assertIsInstance(response['content'], str)

    @httpretty.activate
    def test_do_modify(self):
        url = ''.join((self.files_url, 'foo.txt'))
        msg = {'server_timestamp': time.time()}
        js = json.dumps(msg)
        httpretty.register_uri(httpretty.PUT, url, status=201,
                               body=js,
                               content_type="application/json")

        response = self.cm.do_modify({'filepath': 'foo.txt', 'md5': 'test_md5'})
        self.assertTrue(response['successful'])
        self.assertEqual(response['content'], msg)

    @httpretty.activate
    def test_do_modify_fail(self):
        url = ''.join((self.files_url, 'foo.txt'))
        httpretty.register_uri(httpretty.PUT, url, status=404,
                               content_type="application/json")

        response = self.cm.do_modify({'filepath': 'foo.txt', 'md5': 'test_md5'})
        self.assertFalse(response['successful'])
        self.assertIsInstance(response['content'], str)

    @httpretty.activate
    def test_do_copy(self):
        url = ''.join([self.actions_url, 'copy'])
        d = {'src': 'foo.txt', 'dst': 'folder/foo.txt'}
        msg = {'server_timestamp': time.time()}
        js = json.dumps(msg)
        httpretty.register_uri(httpretty.POST, url, status=201,
                               body=js,
                               content_type="application/json")

        response = self.cm.do_copy(d)
        self.assertTrue(response['successful'])
        self.assertEqual(response['content'], msg)

    @httpretty.activate
    def test_do_copy_fail(self):
        url = ''.join([self.actions_url, 'copy'])
        d = {'src': 'foo.txt', 'dst': 'folder/foo.txt'}
        httpretty.register_uri(httpretty.POST, url, status=404,
                               content_type="application/json")

        response = self.cm.do_copy(d)
        self.assertFalse(response['successful'])
        self.assertIsInstance(response['content'], str)

    @httpretty.activate
    def test_get_server_snapshot(self):
        url = self.files_url
        msg = {'files': 'foo.txt'}
        js = json.dumps(msg)

        httpretty.register_uri(httpretty.GET, url, status=201,
                               body=js,
                               content_type="application/json")

        response = self.cm.do_get_server_snapshot('')
        self.assertTrue(response['successful'])
        self.assertEqual(response['content'], msg)

    @httpretty.activate
    def test_get_server_snapshot_fail(self):
        url = self.files_url

        httpretty.register_uri(httpretty.GET, url, status=404,
                               content_type="application/json")

        response = self.cm.do_get_server_snapshot('')
        self.assertFalse(response['successful'])
        self.assertIsInstance(response['content'], str)

if __name__ == '__main__':
    unittest.main()
