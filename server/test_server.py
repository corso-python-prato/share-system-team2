# !/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import io
import os
import base64
import shutil
import urlparse
import json
import logging

import server

SERVER_API = '/API/V1/'
SERVER_FILES_API = urlparse.urljoin(SERVER_API, 'files/')
SERVER_ACTIONS_API = urlparse.urljoin(SERVER_API, 'actions/')

# Set server logging verbosity
server_verbosity = logging.INFO  # change it manually if you want change the server verbosity
server.logger.setLevel(server_verbosity)
# Very basic logging configuration for this test module:
logging.basicConfig(level=logging.WARNING)

# Test-user account details
REGISTERED_TEST_USER = 'pyboxtestuser', 'pw'
USR, PW = REGISTERED_TEST_USER
# WARNING: this username is reserved for testing purpose ONLY! TODO: make this user not registrable
#create test folders and files for 'files/' api
USER_RELATIVE_DOWNLOAD_FILEPATH = 'testdownload/testfile.txt'
DOWNLOAD_TEST_URL = SERVER_FILES_API + USER_RELATIVE_DOWNLOAD_FILEPATH
USER_RELATIVE_UPLOAD_FILEPATH = 'testupload/testfile.txt'
UPLOAD_TEST_URL = SERVER_FILES_API + USER_RELATIVE_UPLOAD_FILEPATH
UNEXISTING_TEST_URL = SERVER_FILES_API + 'testdownload/unexisting.txt'
#create test folders and files for 'actions/' api
DELETE_TEST_URL = SERVER_ACTIONS_API + 'delete'
DELETE_TEST_FILE_PATH = 'testdelete/testdeletefile.txt'
COPY_TEST_URL = SERVER_ACTIONS_API + 'copy'
SRC_COPY_TEST_FILE_PATH = 'test_copy_src/testcopysrc.txt'
DST_COPY_TEST_FILE_PATH = 'test_copy_dst/testcopydst.txt'
MOVE_TEST_URL = SERVER_ACTIONS_API + 'move'
SRC_MOVE_TEST_FILE_PATH = 'test_move_src/testmovesrc.txt'
DST_MOVE_TEST_FILE_PATH = 'test_move_dst/testmovedst.txt'


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


def _create_file(username, user_relpath, content):
    """
    Create an user file with path <user_relpath> and content <content>
    and return it's last modification time (== creation time).
    :param username: str
    :param user_relpath: str
    :param content: str
    :return: float
    """
    filepath = userpath2serverpath(username, user_relpath)
    dirpath = os.path.dirname(filepath)
    if not os.path.isdir(dirpath):
        os.makedirs(dirpath)
    with open(filepath, 'wb') as fp:
        fp.write(content)
    mtime = os.path.getmtime(filepath)
    return mtime


def create_user_dir(username):
    """
    Create user directory (must not exist)
    :param username:
    :return:
    """
    os.makedirs(userpath2serverpath(username, ''))


def build_testuser_dir(username):
    """
    Create a directory with files and return its structure
    in a list.
    :param username: str
    :return: list
    """
    # md5("foo") = "acbd18db4cc2f85cedef654fccc4a4d8"
    # md5("bar") = "37b51d194a7513e45b56f6524f2d51f2"
    # md5("spam") = "e09f6a7593f8ae3994ea57e1117f67ec"
    file_contents = [
        ('spamfile', 'spam', 'e09f6a7593f8ae3994ea57e1117f67ec'),
        (os.path.join('subdir', 'foofile.txt'), 'foo', 'acbd18db4cc2f85cedef654fccc4a4d8'),
        (os.path.join('subdir', 'barfile.md'), 'bar', '37b51d194a7513e45b56f6524f2d51f2'),
    ]

    user_root = userpath2serverpath(username, '')
    # If directory already exists, destroy it
    if os.path.isdir(user_root):
        shutil.rmtree(user_root)

    os.mkdir(user_root)

    target = {}
    for user_filepath, content, md5 in file_contents:
        _create_file(username, user_filepath, content)
        target[user_filepath] = md5
    return target


def _manually_create_user(username, pw):
    server.userdata[username] = server._encrypt_password(pw)
    create_user_dir(username)


def _manually_remove_user(username):  # TODO: make this from server module
    # WARNING: Removing the test-user manually from db if it exists!
    # (is it the right way to make sure that the test user don't exist?)
    if USR in server.userdata:
        server.userdata.pop(username)
    # Remove user directory if exists!
    user_dirpath = userpath2serverpath(USR, '')
    if os.path.exists(user_dirpath):
        shutil.rmtree(user_dirpath)
        logging.info('"%s" user directory removed' % user_dirpath)
    else:
        logging.info('"%s" user directory does not exist...' % user_dirpath)


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
        _manually_create_user(USR, PW)

        # Create temporary file
        server_filepath = userpath2serverpath(USR, USER_RELATIVE_DOWNLOAD_FILEPATH)
        if not os.path.exists(os.path.dirname(server_filepath)):
            os.makedirs(os.path.dirname(server_filepath))
        with open(server_filepath, 'w') as fp:
            fp.write('some text')

    def tearDown(self):
        server_filepath = userpath2serverpath(USR, USER_RELATIVE_DOWNLOAD_FILEPATH)
        if os.path.exists(server_filepath):
            os.remove(server_filepath)
        _manually_remove_user(USR)

    def test_files_get_with_auth(self):
        """
        Test that server return an OK HTTP code if an authenticated user request
        to download an existing file.
        """
        test = self.app.get(DOWNLOAD_TEST_URL,
                            headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))})
        self.assertEqual(test.status_code, server.HTTP_OK)

    def test_files_get_existing_file_with_wrong_password(self):
        """
        Test that server return a HTTP_UNAUTHORIZED error if
        the user exists but the given password is wrong.
        """
        wrong_password = PW + 'a'
        test = self.app.get(DOWNLOAD_TEST_URL,
                            headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, wrong_password))})
        self.assertEqual(test.status_code, server.HTTP_UNAUTHORIZED)

    def test_files_get_existing_file_with_empty_password(self):
        """
        Test that server return a HTTP_UNAUTHORIZED error if
        the user exists but the password is an empty string.
        """
        test = self.app.get(DOWNLOAD_TEST_URL,
                            headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, ''))})
        self.assertEqual(test.status_code, server.HTTP_UNAUTHORIZED)

    def test_files_get_existing_file_with_empty_username(self):
        """
        Test that server return a HTTP_UNAUTHORIZED error if
        the given user is an empty string and the password is not empty.
        """
        test = self.app.get(DOWNLOAD_TEST_URL,
                            headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format('', PW))})
        self.assertEqual(test.status_code, server.HTTP_UNAUTHORIZED)

    def test_files_get_existing_file_with_unexisting_user(self):
        """
        Test that server return a HTTP_UNAUTHORIZED error if
        the given user does not exist.
        """
        user = 'UnExIsTiNgUsEr'
        assert not user in server.userdata
        test = self.app.get(DOWNLOAD_TEST_URL,
                            headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(user, PW))})
        self.assertEqual(test.status_code, server.HTTP_UNAUTHORIZED)

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

    def test_files_get_snapshot(self):
        """
        Test lato-server user files snapshot.
        """
        # The test user is created in setUp
        target = {server.SNAPSHOT: build_testuser_dir(USR)}
        test = self.app.get(SERVER_FILES_API,
                            headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))},
                            )
        self.assertEqual(test.status_code, server.HTTP_OK)
        obj = json.loads(test.data)
        self.assertEqual(obj, target)

    def test_files_post_with_auth(self):
        """
        Test for authenticated upload.
        """
        uploaded_filepath = userpath2serverpath(USR, USER_RELATIVE_UPLOAD_FILEPATH)
        assert not os.path.exists(uploaded_filepath), '"{}" file is existing'.format(uploaded_filepath)

        test = self.app.post(UPLOAD_TEST_URL,
                             headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))},
                             data=dict(file=(io.BytesIO(b'this is a test'), 'test.pdf'),),
                             follow_redirects=True)
        self.assertEqual(test.status_code, server.HTTP_CREATED)
        self.assertTrue(os.path.isfile(uploaded_filepath))
        os.remove(uploaded_filepath)
        logging.info('"{}" removed'.format(uploaded_filepath))

    def test_files_post_with_not_allowed_path(self):
        """
        Test that creating a directory upper than the user root is not allowed.
        """
        user_filepath = '../../../test/myfile2.dat'  # path forbidden
        url = SERVER_FILES_API + user_filepath
        test = self.app.post(url,
                             headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))},
                             data=dict(file=(io.BytesIO(b'this is a test'), 'test.pdf'),), follow_redirects=True)
        self.assertEqual(test.status_code, server.HTTP_FORBIDDEN)
        self.assertFalse(os.path.isfile(userpath2serverpath(USR, user_filepath)))

    def test_delete_file_path(self):
        """
        Test if a created file is deleted and assures it doesn't exists anymore with assertFalse
        """
        #create file to be deleted
        to_delete_filepath = userpath2serverpath(USR, DELETE_TEST_FILE_PATH)

        _create_file(USR, DELETE_TEST_FILE_PATH, 'this is the file to be deleted')
        #user_filepath = '../../../test/myfile2.dat'  # path forbidden
        test = self.app.post(DELETE_TEST_URL,
                             headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))},
                             data={'filepath':to_delete_filepath}, follow_redirects=True)

        #os.remove(uploaded_filepath)
        self.assertEqual(test.status_code, server.HTTP_OK)
        self.assertFalse(os.path.isfile(to_delete_filepath))

    def test_copy_file_path(self):
        """
        Test if a created source file is copied in a new created destination and assures the source file
        still exists
        """
        #create source file to be copied and its destination
        src_copy_filepath = userpath2serverpath(USR, SRC_COPY_TEST_FILE_PATH)
        dst_copy_filepath = userpath2serverpath(USR, DST_COPY_TEST_FILE_PATH)

        _create_file(USR, SRC_COPY_TEST_FILE_PATH, 'this is the file to be copied')
        _create_file(USR, DST_COPY_TEST_FILE_PATH, 'different other content')

        #user_filepath = '../../../test/myfile2.dat'  # path forbidden
        test = self.app.post(COPY_TEST_URL,
                             headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))},
                             data={'src':src_copy_filepath, 'dst':dst_copy_filepath}, follow_redirects=True)

        #os.remove(uploaded_filepath)
        self.assertEqual(test.status_code, server.HTTP_OK)
        self.assertTrue(os.path.isfile(src_copy_filepath))

    def test_move_file_path(self):
        """
        TTest if a created source file is moved in a new created destination and assures the source file
        doesn't exists after
        """
        #create source file to be moved and its destination
        src_move_filepath = userpath2serverpath(USR, SRC_MOVE_TEST_FILE_PATH)
        dst_move_filepath = userpath2serverpath(USR, DST_MOVE_TEST_FILE_PATH)

        _create_file(USR, SRC_MOVE_TEST_FILE_PATH, 'this is the file to be moved')
        _create_file(USR, DST_MOVE_TEST_FILE_PATH, 'different other content')

        #user_filepath = '../../../test/myfile2.dat'  # path forbidden
        test = self.app.post(MOVE_TEST_URL,
                             headers={'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(USR, PW))},
                             data={'src':src_move_filepath, 'dst':dst_move_filepath}, follow_redirects=True)

        #os.remove(uploaded_filepath)
        self.assertEqual(test.status_code, server.HTTP_OK)
        self.assertFalse(os.path.isfile(src_move_filepath))


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
        test = self.app.post(urlparse.urljoin(SERVER_API, 'signup'),
                             data={'username': USR, 'password': PW})
        self.assertEqual(test.status_code, server.HTTP_CREATED)


if __name__ == '__main__':
    unittest.main()
