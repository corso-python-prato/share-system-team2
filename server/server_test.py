# !/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import io
import os
import base64
import shutil

import server

SERVER_API = '/API/V1'
SERVER_FILES_API = os.path.join(SERVER_API, 'files/')

# Test-user stuff
REGISTERED_TEST_USER = 'pyboxtestuser', 'pw'
USR, PW = REGISTERED_TEST_USER
# WARNING: this username is reserved for testing purpose ONLY! TODO: make this user not registrable
USER_RELATIVE_DOWNLOAD_FILEPATH = 'testdownload/testfile.txt'
DOWNLOAD_TEST_URL = os.path.join(SERVER_FILES_API, USER_RELATIVE_DOWNLOAD_FILEPATH)
USER_RELATIVE_UPLOAD_FILEPATH = 'testupload/testfile.txt'
UPLOAD_TEST_URL = os.path.join(SERVER_FILES_API, USER_RELATIVE_UPLOAD_FILEPATH)
UNEXISTING_TEST_URL = os.path.join(SERVER_FILES_API, 'testdownload/unexisting.txt')


def userpath2serverpath(username, path):
    """
    Given an username and its relative path, return the
    corrisponding path in the server.
    :param username: str
    :param path: str
    :return: str
    """
    # This function depends on server module
    # TODO: define this function into the server module and call from it
    return os.path.realpath(os.path.join(server.FILE_ROOT, username, path))


def _manually_remove_user(username):  # TODO: make this from server module
    # WARNING: Removing the test-user manually from db if it exists!
    # (is it the right way to make sure that the test user don't exist?)
    if USR in server.userdata:
        server.userdata.pop(username)
    # Remove user directory if exists!
    user_dirpath = userpath2serverpath(USR, '')
    if os.path.exists(user_dirpath):
        shutil.rmtree(user_dirpath)
        print '"%s" user directory removed' % user_dirpath
    else:
        print '"%s" user directory does not exist...' % user_dirpath


class TestRequests(unittest.TestCase):
    def setUp(self):
        """
        Create an user with a POST method and create the test file to test the download from server.
        """
        self.app = server.app.test_client()
        self.app.testing = True

        # To see the tracebacks in case of 500 server error!
        server.app.config.update(TESTING=True)

        _manually_remove_user(USR)
        # Create test user
        self.app.post(os.path.join(SERVER_API, 'signup'),
                      data={'username': USR, 'password': PW})

        # Create temporary file
        server_filepath = userpath2serverpath(USR, USER_RELATIVE_DOWNLOAD_FILEPATH)
        if not os.path.exists(os.path.dirname(server_filepath)):
            os.makedirs(os.path.dirname(server_filepath))
        with open(server_filepath, 'w') as fp:
            fp.write('some text')

    def tearDown(self):
        server_filepath = userpath2serverpath(USR, USER_RELATIVE_DOWNLOAD_FILEPATH)
        os.remove(server_filepath)
        print 'deleted temporary resource', server_filepath
        _manually_remove_user(USR)

    def test_files_get_with_auth(self):
        """
        Test that server return an OK HTTP code if an authenticated user request
        to download an existing file.
        """
        test = self.app.get(DOWNLOAD_TEST_URL,
                            headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))})
        self.assertEqual(test.status_code, server.HTTP_OK)

    def test_files_get_without_auth(self):
        """
        Test unauthorized download of an existsing file.
        """
        # TODO: ensure that the file exists
        test = self.app.get(DOWNLOAD_TEST_URL)
        self.assertEqual(test.status_code, server.HTTP_UNAUTHORIZED)

    def test_files_get_with_not_existing_file(self):
        """
        Test that error 404 is correctly returned if an authenticated user try to download
        a file that does not exist.
        """
        test = self.app.get(UNEXISTING_TEST_URL,
                            headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))})
        self.assertEqual(test.status_code, server.HTTP_NOT_FOUND)

    def test_files_post_with_auth(self):
        """
        Test for authenticated upload.
        """
        uploaded_filepath = userpath2serverpath(USR, USER_RELATIVE_UPLOAD_FILEPATH)
        assert not os.path.exists(uploaded_filepath), '"{}" file is existing'.format(uploaded_filepath)

        test = self.app.post(UPLOAD_TEST_URL,
                             headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))},
                             data=dict(file=(io.BytesIO(b"this is a test"), "test.pdf"),),
                             follow_redirects=True)
        self.assertEqual(test.status_code, server.HTTP_CREATED)
        self.assertTrue(os.path.isfile(uploaded_filepath))
        os.remove(uploaded_filepath)
        print('"{}" removed'.format(uploaded_filepath))

    def test_files_post_with_not_allowed_path(self):
        """
        Test that creating a directory upper than the user root is not allowed.
        """
        user_filepath = "../../../test/myfile2.dat"  # path forbidden
        test = self.app.post(os.path.join(SERVER_FILES_API, user_filepath),
                             headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))},
                             data=dict(file=(io.BytesIO(b"this is a test"), "test.pdf"),), follow_redirects=True)
        self.assertEqual(test.status_code, server.HTTP_FORBIDDEN)
        self.assertFalse(os.path.isfile(userpath2serverpath(USR, user_filepath)))


class TestUsers(unittest.TestCase):
    def setUp(self):
        self.app = server.app.test_client()
        self.app.testing = True

        # To see the tracebacks in case of 500 server error!
        server.app.config.update(TESTING=True)

        _manually_remove_user(USR)

    def test_signup(self):
        """
        Test for registration of a new user.
        """
        test = self.app.post(os.path.join(SERVER_API, 'signup'),
                             data={'username': USR, 'password': PW})
        self.assertEqual(test.status_code, server.HTTP_CREATED)


if __name__ == "__main__":
    unittest.main()
