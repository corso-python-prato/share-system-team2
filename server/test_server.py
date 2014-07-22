#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
server test module

Every TestCase class should use the <TEST_DIR> directory. To do it, just call 'setup_test_dir()' in the setUp method and
'tear_down_test_dir()' in the tearDown one.
"""
import unittest
import os
import base64
import shutil
import urlparse
import json
import logging
import hashlib
import tempfile
import random
import string

import server
from server import userpath2serverpath

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_ACCEPTED = 202
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409

start_dir = os.getcwd()

TEST_DIR = 'server_test'

SERVER_API = '/API/V1/'
SERVER_FILES_API = urlparse.urljoin(SERVER_API, 'files/')
SERVER_ACTIONS_API = urlparse.urljoin(SERVER_API, 'actions/')

# Set server logging verbosity
server_verbosity = logging.WARNING  # change it manually if you want change the server verbosity
server.logger.setLevel(server_verbosity)
# Very basic logging configuration for this test module:
logging.basicConfig(level=logging.WARNING)

# Test-user account details
REGISTERED_TEST_USER = 'pyboxtestuser', 'pw'
USR, PW = REGISTERED_TEST_USER


def pick_rand_str(length, possible_chars=string.ascii_lowercase):
    return ''.join([random.choice(possible_chars) for _ in xrange(length)])


def pick_rand_pw(length=8):
    possible_chars = string.letters + string.punctuation + string.digits
    return pick_rand_str(length, possible_chars)


def pick_rand_email():
    res = '{}@{}.{}'.format(pick_rand_str(random.randrange(3, 12)),
                            pick_rand_str(random.randrange(3, 8)),
                            pick_rand_str(random.randrange(2, 4)))
    return res
    # \b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}\b


def make_basicauth_headers(user, pwd):
    return {'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(user, pwd))}


def _create_file(username, user_relpath, content, update_userdata=True):
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
    mtime = server.now_timestamp()
    if update_userdata:
        server.userdata[username][server.SNAPSHOT][user_relpath] = [mtime,
                                                                    server.calculate_file_md5(open(filepath, 'rb'))]
    return mtime


def create_user_dir(username):
    """
    Create user directory (must not exist)
    :param username:
    :return:
    """
    os.makedirs(userpath2serverpath(username))


def build_tstuser_dir(username):
    """
    Create a directory with files and return its structure
    in a list.
    :param username: str
    :return: tuple
    """
    # md5("foo") = "acbd18db4cc2f85cedef654fccc4a4d8"
    # md5("bar") = "37b51d194a7513e45b56f6524f2d51f2"
    # md5("spam") = "e09f6a7593f8ae3994ea57e1117f67ec"
    file_contents = [
        ('spamfile', 'spam', 'e09f6a7593f8ae3994ea57e1117f67ec'),
        (os.path.join('subdir', 'foofile.txt'), 'foo', 'acbd18db4cc2f85cedef654fccc4a4d8'),
        (os.path.join('subdir', 'barfile.md'), 'bar', '37b51d194a7513e45b56f6524f2d51f2'),
    ]

    user_root = userpath2serverpath(username)
    # If directory already exists, destroy it
    if os.path.isdir(user_root):
        shutil.rmtree(user_root)
    os.mkdir(user_root)
    expected_timestamp = None
    expected_snapshot = {}
    for user_filepath, content, md5 in file_contents:
        expected_timestamp = int(_create_file(username, user_filepath, content))
        expected_snapshot[user_filepath] = [expected_timestamp, unicode(md5)]
    return expected_timestamp, expected_snapshot


def _manually_create_user(username, pw):
    """
    Create an user, its server directory, and return its userdata dictionary.
    :param username: str
    :param pw: str
    :return: dict
    """
    enc_pass = server._encrypt_password(pw)
    # Create user directory with default structure (use the server function)
    user_dir_state = server.init_user_directory(username)
    single_user_data = user_dir_state
    single_user_data[server.PWD] = enc_pass
    single_user_data[server.USER_CREATION_TIME] = server.now_timestamp()
    server.userdata[username] = single_user_data
    return single_user_data


def _manually_remove_user(username):  # TODO: make this from server module?
    """
    Remove user dictionary from server <userdata>, if exist,
    and remove its directory from disk, if exist.
    :param username: str
    """
    if USR in server.userdata:
        server.userdata.pop(username)
    # Remove user directory if exists!
    user_dirpath = userpath2serverpath(USR)
    if os.path.exists(user_dirpath):
        shutil.rmtree(user_dirpath)
        logging.debug('"%s" user directory removed' % user_dirpath)


def setup_test_dir():
    """
    Create (if needed) <TEST_DIR> directory starting from current directory and change current directory to the new one.
    """
    try:
        os.mkdir(TEST_DIR)
    except OSError:
        pass

    os.chdir(TEST_DIR)


def tear_down_test_dir():
    """
    Return to initial directory and remove the <TEST_DIR> one.
    """
    os.chdir(start_dir)
    shutil.rmtree(TEST_DIR)


def _make_temp_file():
    """
    Create temporary file for testing
    NB: the file sent with test_client() must be with name
    :return: First value is a FileObject and second value the relative md5
    """
    temp_file = tempfile.NamedTemporaryFile()
    temp_file.write('this is a test')
    temp_file.seek(0)
    test_md5 = hashlib.md5('this is a test').hexdigest()
    return temp_file, test_md5


class TestRequests(unittest.TestCase):
    def setUp(self):
        """
        Create an user and create the test file to test the download from server.
        """
        setup_test_dir()

        self.app = server.app.test_client()
        self.app.testing = True

        _manually_remove_user(USR)
        _manually_create_user(USR, PW)

    def tearDown(self):
        _manually_remove_user(USR)
        tear_down_test_dir()

    def test_files_post_with_auth(self):
        """
        Test for authenticated upload.
        """
        user_relative_upload_filepath = 'testupload/testfile.txt'
        upload_test_url = SERVER_FILES_API + user_relative_upload_filepath
        uploaded_filepath = userpath2serverpath(USR, user_relative_upload_filepath)
        assert not os.path.exists(uploaded_filepath), '"{}" file is existing'.format(uploaded_filepath)
        # Create temporary file for test
        test_file, test_md5 = _make_temp_file()
        try:
            test = self.app.post(upload_test_url,
                                 headers=make_basicauth_headers(USR, PW),
                                 data={'file': test_file, 'md5': test_md5},
                                 follow_redirects=True)
        finally:
            test_file.close()
        self.assertEqual(test.status_code, server.HTTP_CREATED)
        self.assertTrue(os.path.isfile(uploaded_filepath))
        # check that uploaded path exists in username files dict
        self.assertIn(user_relative_upload_filepath, server.userdata[USR][server.SNAPSHOT])
        os.remove(uploaded_filepath)
        logging.info('"{}" removed'.format(uploaded_filepath))

    def test_files_post_with_not_allowed_path(self):
        """
        Test that creating a directory upper than the user root is not allowed.
        """
        user_filepath = '../../../test/myfile2.dat'  # path forbidden
        url = SERVER_FILES_API + user_filepath
        # Create temporary file for test
        test_file, test_md5 = _make_temp_file()
        try:
            test = self.app.post(url,
                                 headers=make_basicauth_headers(USR, PW),
                                 data={'file': test_file, 'md5': test_md5},
                                 follow_redirects=True)
        finally:
            test_file.close()
        self.assertEqual(test.status_code, server.HTTP_FORBIDDEN)
        self.assertFalse(os.path.isfile(userpath2serverpath(USR, user_filepath)))
        # check that uploaded path NOT exists in username files dict
        self.assertNotIn(user_filepath, server.userdata[USR][server.SNAPSHOT])

    def test_files_post_with_existent_path(self):
        """
        Test the creation of file that already exists.
        """
        path = 'test_put/file_to_change.txt'  # path already existent
        _create_file(USR, path, 'I already exist! Don\'t erase me!')
        to_created_filepath = userpath2serverpath(USR, path)
        old_content = open(to_created_filepath).read()
        old_md5 = server.userdata[USR][server.SNAPSHOT][path][1]

        url = SERVER_FILES_API + path

        # Create temporary file for test
        test_file, test_md5 = _make_temp_file()
        try:
            test = self.app.post(url,
                                 headers=make_basicauth_headers(USR, PW),
                                 data={'file': test_file, 'md5': test_md5},
                                 follow_redirects=True)
        finally:
            test_file.close()
        self.assertEqual(test.status_code, server.HTTP_FORBIDDEN)
        new_content = open(to_created_filepath).read()
        self.assertEqual(old_content, new_content)
        new_md5 = server.userdata[USR][server.SNAPSHOT][path][1]
        self.assertEqual(old_md5, new_md5)

    def test_files_post_with_bad_md5(self):
        """
        Test upload with bad md5.
        """
        user_relative_upload_filepath = 'testupload/testfile.txt'
        upload_test_url = SERVER_FILES_API + user_relative_upload_filepath
        uploaded_filepath = userpath2serverpath(USR, user_relative_upload_filepath)
        assert not os.path.exists(uploaded_filepath), '"{}" file is existing'.format(uploaded_filepath)
        # Create temporary file for test
        test_file, not_used_md5 = _make_temp_file()

        # Create fake md5 and send it instead the right md5
        fake_md5 = 'sent_bad_md5'
        try:
            test = self.app.post(upload_test_url,
                                 headers=make_basicauth_headers(USR, PW),
                                 data={'file': test_file, 'md5': fake_md5},
                                 follow_redirects=True)
        finally:
            test_file.close()
        self.assertEqual(test.status_code, server.HTTP_CONFLICT)
        self.assertFalse(os.path.isfile(userpath2serverpath(USR, user_relative_upload_filepath)))

        # check that uploaded path NOT exists in username files dict
        self.assertNotIn(user_relative_upload_filepath, server.userdata[USR][server.SNAPSHOT])

    def test_files_put_with_auth(self):
        """
        Test put. File content and stored md5 must be changed.
        """
        path = 'test_put/file_to_change.txt'
        _create_file(USR, path, 'I will change')
        to_modify_filepath = userpath2serverpath(USR, path)
        old_content = open(to_modify_filepath).read()
        old_md5 = server.userdata[USR][server.SNAPSHOT][path][1]

        url = SERVER_FILES_API + path
        # Create temporary file for test
        test_file, not_used_md5 = _make_temp_file()

        # Create fake md5 and send it instead the right md5
        fake_md5 = 'sent_bad_md5'
        try:
            test = self.app.put(url,
                                headers=make_basicauth_headers(USR, PW),
                                data={'file': test_file, 'md5': fake_md5},
                                follow_redirects=True)
        finally:
            test_file.close()
        new_content = open(to_modify_filepath).read()
        self.assertEqual(old_content, new_content)
        new_md5 = server.userdata[USR][server.SNAPSHOT][path][1]
        self.assertEqual(old_md5, new_md5)
        self.assertEqual(test.status_code, server.HTTP_CONFLICT)

    def test_files_put_of_not_existing_file(self):
        """
        Test modify of not existing file..
        """
        path = 'test_put/file_not_existent.txt'  # not existent path
        to_modify_filepath = userpath2serverpath(USR, path)

        url = SERVER_FILES_API + path
        # Create temporary file for test
        test_file, test_md5 = _make_temp_file()
        try:
            test = self.app.put(url,
                                headers=make_basicauth_headers(USR, PW),
                                data={'file': test_file, 'md5': test_md5},
                                follow_redirects=True)
        finally:
            test_file.close()

        self.assertEqual(test.status_code, server.HTTP_NOT_FOUND)
        self.assertNotIn(to_modify_filepath, server.userdata[USR][server.SNAPSHOT])

    def test_files_put_with_bad_md5(self):
        """
        Test modify with bad md5.
        """
        path = 'test_put/file_to_change.txt'
        _create_file(USR, path, 'I will NOT change')
        to_modify_filepath = userpath2serverpath(USR, path)
        old_content = open(to_modify_filepath).read()
        old_md5 = server.userdata[USR][server.SNAPSHOT][path][1]

        url = SERVER_FILES_API + path
        # Create temporary file for test
        test_file, test_md5 = _make_temp_file()
        try:
            test = self.app.put(url,
                                headers=make_basicauth_headers(USR, PW),
                                data={'file': test_file, 'md5': test_md5},
                                follow_redirects=True)
        finally:
            test_file.close()
        new_content = open(to_modify_filepath).read()
        self.assertNotEqual(old_content, new_content)
        new_md5 = server.userdata[USR][server.SNAPSHOT][path][1]
        self.assertNotEqual(old_md5, new_md5)
        self.assertEqual(test.status_code, server.HTTP_CREATED)  # 200 or 201 (OK or created)?

    def test_delete_file_path(self):
        """
        Test if a created file is deleted and assures it doesn't exists anymore with assertFalse
        """
        # create file to be deleted
        delete_test_url = SERVER_ACTIONS_API + 'delete'
        delete_test_file_path = 'testdelete/testdeletefile.txt'
        to_delete_filepath = userpath2serverpath(USR, delete_test_file_path)

        _create_file(USR, delete_test_file_path, 'this is the file to be deleted')

        test = self.app.post(delete_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'filepath': delete_test_file_path}, follow_redirects=True)

        self.assertEqual(test.status_code, server.HTTP_OK)
        self.assertFalse(os.path.isfile(to_delete_filepath))
        self.assertNotIn(delete_test_file_path, server.userdata[USR][server.SNAPSHOT])

    def test_delete_file_path_with_tricky_filepath(self):
        """
        Test the deleting action with a path that can fall in other user directories or upper.
        """
        delete_test_url = SERVER_ACTIONS_API + 'delete'
        tricky_to_delete_test_filepath = 'testdelete/../../testdeletefile.txt'

        test = self.app.post(delete_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'filepath': tricky_to_delete_test_filepath}, follow_redirects=True)

        self.assertEqual(test.status_code, server.HTTP_FORBIDDEN)

    def test_delete_file_path_with_unexisting_filepath(self):
        """
        Test if delete action returns HTTP_NOT_FOUND when trying to remove an unexisting file.
        """
        delete_test_url = SERVER_ACTIONS_API + 'delete'
        wrong_to_delete_test_filepath = 'testdelete/unexistingfile.dat'

        test = self.app.post(delete_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'filepath': wrong_to_delete_test_filepath}, follow_redirects=True)
        self.assertEqual(test.status_code, HTTP_NOT_FOUND)

    def test_copy_file_path(self):
        """
        Test if a created source file is copied in a new created destination and assures the source file
        still exists
        """
        copy_test_url = SERVER_ACTIONS_API + 'copy'
        src_copy_test_file_path = 'test_copy_src/testcopysrc.txt'
        dst_copy_test_file_path = 'test_copy_dst/testcopydst.txt'
        # Create source file to be copied and its destination.
        src_copy_filepath = userpath2serverpath(USR, src_copy_test_file_path)

        _create_file(USR, src_copy_test_file_path, 'this is the file to be copied')
        _create_file(USR, dst_copy_test_file_path, 'different other content')

        test = self.app.post(copy_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'src': src_copy_test_file_path, 'dst': dst_copy_test_file_path},
                             follow_redirects=True)

        self.assertEqual(test.status_code, server.HTTP_OK)
        self.assertTrue(os.path.isfile(src_copy_filepath))

    def test_copy_file_path_with_tricky_filepaths(self):
        """
        Test the copy action with source and destination paths that can fall in other user directories or upper.
        """
        copy_test_url = SERVER_ACTIONS_API + 'copy'
        tricky_src_copy_test_file_path = 'test_copy_src/../../testcopysrc.txt'
        tricky_dst_copy_test_file_path = 'test_copy_dst/../../testcopydst.txt'

        test = self.app.post(copy_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'src': tricky_src_copy_test_file_path, 'dst': tricky_dst_copy_test_file_path},
                             follow_redirects=True)

        self.assertEqual(test.status_code, server.HTTP_FORBIDDEN)

    def test_copy_file_path_with_unexisting_destinationfile(self):
        """
        Test the creation of a destination file if this one doesn't exists from the beginning.
        """
        copy_test_url = SERVER_ACTIONS_API + 'copy'
        src_copy_test_file_path = 'test_copy_src/testcopysrc.txt'
        dst_copy_test_file_path = 'test_copy_dst/testcopydst.txt'
        # Create source file to be copied and its destination.
        src_copy_filepath = userpath2serverpath(USR, src_copy_test_file_path)

        _create_file(USR, src_copy_test_file_path, 'this is the file to be copied')

        test = self.app.post(copy_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'src': src_copy_test_file_path, 'dst': dst_copy_test_file_path},
                             follow_redirects=True)

        self.assertEqual(test.status_code, server.HTTP_OK)

    def test_copy_file_path_with_unexisting_source(self):
        """
        Test if copy action returns HTTP_NOT_FOUND when trying to copy from an unexisting source file.
        """
        copy_test_url = SERVER_ACTIONS_API + 'copy'
        unexisting_src_copy_test_file_path = 'test_copy_src/unexistingcopysrc.txt'
        dst_copy_test_file_path = 'test_copy_dst/testcopydst.txt'

        test = self.app.post(copy_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'src': unexisting_src_copy_test_file_path, 'dst': dst_copy_test_file_path},
                             follow_redirects=True)

        self.assertEqual(test.status_code, HTTP_NOT_FOUND)

    def test_move_file_path(self):
        """
        Test if a created source file is moved in a new created destination and assures the source file
        doesn't exists after
        """
        move_test_url = SERVER_ACTIONS_API + 'move'
        src_move_test_file_path = 'test_move_src/testmovesrc.txt'
        dst_move_test_file_path = 'test_move_dst/testmovedst.txt'
        # create source file to be moved and its destination
        src_move_filepath = userpath2serverpath(USR, src_move_test_file_path)

        _create_file(USR, src_move_test_file_path, 'this is the file to be moved')

        test = self.app.post(move_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'src': src_move_test_file_path, 'dst': dst_move_test_file_path},
                             follow_redirects=True)

        self.assertEqual(test.status_code, server.HTTP_OK)
        self.assertFalse(os.path.isfile(src_move_filepath))

    def test_move_file_path_with_wrong_cmd(self):
        """
        Test if commands (delete, copy, move) exist, otherwise KeyError and throw abort.
        """
        move_test_url = SERVER_ACTIONS_API + 'wrong_cmd'
        src_move_test_file_path = 'test_move_src/testmovesrc.txt'
        dst_move_test_file_path = 'test_move_dst/testmovedst.txt'
        # create source file to be moved and its destination
        _create_file(USR, src_move_test_file_path, 'this is the file to be moved')

        test = self.app.post(move_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'src': src_move_test_file_path, 'dst': dst_move_test_file_path},
                             follow_redirects=True)

        self.assertEqual(test.status_code, server.HTTP_NOT_FOUND)

    def test_move_file_path_with_tricky_filepaths(self):
        """
        Test the move action with source and destination paths that can fall in other user directories or upper.
        """
        move_test_url = SERVER_ACTIONS_API + 'move'
        tricky_src_move_test_file_path = 'test_move_src/../../testmovesrc.txt'
        tricky_dst_move_test_file_path = 'test_move_dst/../../testmovedst.txt'

        test = self.app.post(move_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'src': tricky_src_move_test_file_path, 'dst': tricky_dst_move_test_file_path},
                             follow_redirects=True)

        self.assertEqual(test.status_code, server.HTTP_FORBIDDEN)

    def test_move_file_path_with_unexisting_source(self):
        """
        Test if move action returns HTTP_NOT_FOUND when trying to move from an unexisting source file.
        """
        move_test_url = SERVER_ACTIONS_API + 'move'
        unexisting_src_move_test_file_path = 'test_move_src/unexistingmovesrc.txt'
        dst_move_test_file_path = 'test_move_dst/testmovedst.txt'

        test = self.app.post(move_test_url,
                             headers=make_basicauth_headers(USR, PW),
                             data={'src': unexisting_src_move_test_file_path, 'dst': dst_move_test_file_path},
                             follow_redirects=True)

        self.assertEqual(test.status_code, HTTP_NOT_FOUND)


class TestGetRequests(unittest.TestCase):
    """
    Test get requests.
    """
    USER_RELATIVE_DOWNLOAD_FILEPATH = 'testdownload/testfile.txt'
    DOWNLOAD_TEST_URL = SERVER_FILES_API + USER_RELATIVE_DOWNLOAD_FILEPATH

    def setUp(self):
        """
        Create an user with a POST method and create the test file to test the download from server.
        """
        setup_test_dir()

        self.app = server.app.test_client()
        self.app.testing = True

        _manually_remove_user(USR)
        _manually_create_user(USR, PW)
        _create_file(USR, self.USER_RELATIVE_DOWNLOAD_FILEPATH, 'some text')

    def tearDown(self):
        server_filepath = userpath2serverpath(USR, self.USER_RELATIVE_DOWNLOAD_FILEPATH)
        if os.path.exists(server_filepath):
            os.remove(server_filepath)
        _manually_remove_user(USR)
        tear_down_test_dir()

    def test_files_get_with_auth(self):
        """
        Test that server return an OK HTTP code if an authenticated user request
        to download an existing file.
        """
        test = self.app.get(self.DOWNLOAD_TEST_URL,
                            headers=make_basicauth_headers(USR, PW))
        self.assertEqual(test.status_code, server.HTTP_OK)

    def test_files_get_existing_file_with_wrong_password(self):
        """
        Test that server return a HTTP_UNAUTHORIZED error if
        the user exists but the given password is wrong.
        """
        wrong_password = PW + 'a'
        test = self.app.get(self.DOWNLOAD_TEST_URL,
                            headers=make_basicauth_headers(USR, wrong_password))
        self.assertEqual(test.status_code, server.HTTP_UNAUTHORIZED)

    def test_files_get_existing_file_with_empty_password(self):
        """
        Test that server return a HTTP_UNAUTHORIZED error if
        the user exists but the password is an empty string.
        """
        test = self.app.get(self.DOWNLOAD_TEST_URL,
                            headers=make_basicauth_headers(USR, ''))
        self.assertEqual(test.status_code, server.HTTP_UNAUTHORIZED)

    def test_files_get_existing_file_with_empty_username(self):
        """
        Test that server return a HTTP_UNAUTHORIZED error if
        the given user is an empty string and the password is not empty.
        """
        test = self.app.get(self.DOWNLOAD_TEST_URL,
                            headers=make_basicauth_headers('', PW))
        self.assertEqual(test.status_code, server.HTTP_UNAUTHORIZED)

    def test_files_get_existing_file_with_unexisting_user(self):
        """
        Test that server return a HTTP_UNAUTHORIZED error if
        the given user does not exist.
        """
        user = 'UnExIsTiNgUsEr'
        assert user not in server.userdata
        test = self.app.get(self.DOWNLOAD_TEST_URL,
                            headers=make_basicauth_headers(user, PW))
        self.assertEqual(test.status_code, server.HTTP_UNAUTHORIZED)

    def test_files_get_without_auth(self):
        """
        Test unauthorized download of an existsing file.
        """
        # TODO: ensure that the file exists
        test = self.app.get(self.DOWNLOAD_TEST_URL)
        self.assertEqual(test.status_code, server.HTTP_UNAUTHORIZED)

    def test_files_get_with_not_existing_file(self):
        """
        Test that error 404 is correctly returned if an authenticated user try to download
        a file that does not exist.
        """
        test = self.app.get(SERVER_FILES_API + 'testdownload/unexisting.txt',
                            headers=make_basicauth_headers(USR, PW))
        self.assertEqual(test.status_code, server.HTTP_NOT_FOUND)

    def test_files_get_with_not_existing_directory(self):
        """
        Test that error 404 is correctly returned if an authenticated user try to download
        from an unexisting directory.
        """
        test = self.app.get(SERVER_FILES_API + 'unexisting/unexisting.txt',
                            headers=make_basicauth_headers(USR, PW))
        self.assertEqual(test.status_code, server.HTTP_NOT_FOUND)

    def test_files_get_with_tricky_file(self):
        """
        Test that error 403 is correctly returned if an authenticated user try to download
        a file that can fall in other user directories or upper.
        """
        test = self.app.get(SERVER_FILES_API + 'testdownload/../../testfile.txt',
                            headers=make_basicauth_headers(USR, PW))
        self.assertEqual(test.status_code, server.HTTP_FORBIDDEN)

    def test_files_get_snapshot(self):
        """
        Test server-side user files snapshot.
        """
        # The test user is created in setUp

        expected_timestamp = server.userdata[USR]['server_timestamp']
        expected_snapshot = server.userdata[USR]['files']
        target = {server.LAST_SERVER_TIMESTAMP: expected_timestamp,
                  server.SNAPSHOT: expected_snapshot}
        test = self.app.get(SERVER_FILES_API,
                            headers=make_basicauth_headers(USR, PW))
        self.assertEqual(test.status_code, server.HTTP_OK)
        obj = json.loads(test.data)
        self.assertEqual(obj, target)


class TestUsersPost(unittest.TestCase):
    def setUp(self):
        setup_test_dir()
        server.reset_userdata()

        self.app = server.app.test_client()
        self.app.testing = True

        self.username = 'superpippo@topoliniamail.com'
        self.password = 'superpass'
        self.user_dirpath = userpath2serverpath(self.username)

    def tearDown(self):
        tear_down_test_dir()

    def test_repeated_post(self):
        """
        Post a new user creation 3 times --> permitted.
        """
        for i in range(3):
            # The Users.post (signup request) is repeatable
            test = self.app.post(urlparse.urljoin(SERVER_API, 'users/' + self.username),
                                 data={'password': self.password})

            # Test that user is added to <pending_users>
            self.assertIn(self.username, server.pending_users.keys())
            self.assertEqual(test.status_code, HTTP_OK)

    def test_user_already_existing(self):
        """
        Existing user --> 409.
        """
        _manually_create_user(self.username, self.password)

        test = self.app.post(urlparse.urljoin(SERVER_API, 'users/' + self.username),
                             data={'password': self.password})

        self.assertEqual(test.status_code, HTTP_CONFLICT)

    def test_activation_email(self):
        """
        Activation mail must be sent to the right recipient and *a line* of its body must be the activation code.
        """
        with server.mail.record_messages() as outbox:
            resp = self.app.post(urlparse.urljoin(SERVER_API, 'users/' + self.username),
                                 data={'password': self.password})
        # Retrieve the generated activation code
        activation_code = server.pending_users[self.username]['activation_code']

        self.assertEqual(len(outbox), 1)
        body = outbox[0].body
        recipients = outbox[0].recipients
        self.assertEqual(recipients, [self.username])
        self.assertIn(activation_code, body.splitlines())


class TestUsersPut(unittest.TestCase):
    def setUp(self):
        setup_test_dir()
        server.reset_userdata()

        self.app = server.app.test_client()
        self.app.testing = True

        self.username = 'superpippo@topoliniamail.com'
        self.password = 'superpass'
        self.user_dirpath = userpath2serverpath(self.username)
        assert self.username not in server.pending_users
        assert not os.path.exists(self.user_dirpath)

        # The Users.post (signup request) is repeatable
        resp = self.app.post(urlparse.urljoin(SERVER_API, 'users/' + self.username),
                             data={'password': self.password})

        # Retrieve the generated activation code
        self.activation_code = server.pending_users[self.username]['activation_code']

    def tearDown(self):
        tear_down_test_dir()

    def test_unexisting_username(self):
        """
        Not existing username and existing activation_code.
        """
        unexisting_user = 'unexisting'
        test = self.app.put(urlparse.urljoin(SERVER_API, 'users/' + unexisting_user),
                            data={'activation_code': self.activation_code})

        self.assertEqual(test.status_code, HTTP_NOT_FOUND)
        self.assertNotIn(unexisting_user, server.userdata.keys())
        self.assertFalse(os.path.exists(userpath2serverpath(unexisting_user)))

    def test_wrong_activation_code(self):
        """
        Wrong activation code
        """
        test = self.app.put(urlparse.urljoin(SERVER_API, 'users/' + self.username),
                            data={'activation_code': 'fake activation code'})
        self.assertEqual(test.status_code, HTTP_NOT_FOUND)
        self.assertNotIn(self.username, server.userdata.keys())
        self.assertFalse(os.path.exists(self.user_dirpath))

    def test_ok(self):
        """
        Right activation code --> success.
        """
        # Put with correct activation code
        test = self.app.put(urlparse.urljoin(SERVER_API, 'users/' + self.username),
                            data={'activation_code': self.activation_code})

        self.assertIn(self.username, server.userdata.keys())
        self.assertTrue(os.path.exists(self.user_dirpath))
        self.assertNotIn(self.username, server.pending_users.keys())
        self.assertEqual(test.status_code, HTTP_CREATED)


class TestUsersDelete(unittest.TestCase):
    def setUp(self):
        setup_test_dir()
        server.reset_userdata()

        self.app = server.app.test_client()
        self.app.testing = True

    def tearDown(self):
        tear_down_test_dir()

    def test_delete_user(self):
        """
        User deletion.
        """
        # Creating user to delete on-the-fly (TODO: pre-load instead)
        _manually_create_user(USR, PW)
        user_dirpath = userpath2serverpath(USR)
        # Really created?
        assert USR in server.userdata, 'Utente "{}" non risulta tra i dati'.format(USR)  # TODO: translate
        assert os.path.exists(user_dirpath), 'Directory utente "{}" non trovata'.format(USR)  # TODO: translate

        # Test FORBIDDEN case (removing other users)
        url = SERVER_API + 'users/' + 'otheruser'
        test = self.app.delete(url,
                               headers=make_basicauth_headers(USR, PW))
        self.assertEqual(test.status_code, server.HTTP_FORBIDDEN)

        # Test OK case
        url = SERVER_API + 'users/' + USR
        test = self.app.delete(url,
                               headers=make_basicauth_headers(USR, PW))

        self.assertNotIn(USR, server.userdata)
        self.assertEqual(test.status_code, server.HTTP_OK)
        self.assertFalse(os.path.exists(user_dirpath))


class TestUsersGet(unittest.TestCase):
    def setUp(self):
        setup_test_dir()
        server.reset_userdata()
        self.app = server.app.test_client()
        self.app.testing = True

    def tearDown(self):
        tear_down_test_dir()

    def test_get_self(self):
        username = 'pippo@topolinia.com'
        pw = pick_rand_pw()
        _manually_create_user(username, pw)
        url = SERVER_API + 'users/' + username
        test = self.app.get(url, headers=make_basicauth_headers(username, pw))
        self.assertEqual(test.status_code, HTTP_OK)

    def test_get_other(self):
        username = 'pippo@topolinia.com'
        other_username = 'a' + username
        pw = pick_rand_pw()
        _manually_create_user(username, pw)
        url = SERVER_API + 'users/' + other_username
        test = self.app.get(url, headers=make_basicauth_headers(username, pw))
        self.assertEqual(test.status_code, HTTP_FORBIDDEN)


class TestUsersResetPassword(unittest.TestCase):
    def setUp(self):
        setup_test_dir()
        server.reset_userdata()
        self.app = server.app.test_client()
        self.app.testing = True

        self.active_user = 'Attivo'
        _manually_create_user(self.active_user, pick_rand_pw(8))
        self.pending_user = 'Pendente'
        server.pending_users[self.pending_user] = {'timestamp': server.now_timestamp(),
                                                   'activation_code': 'fake-activation-code'}

    def test_active_user(self):
        url = SERVER_API + 'users/{}/reset'.format(self.active_user)
        new_password = pick_rand_pw(10)
        test = self.app.post(url,
                             data={'password': new_password})
        self.assertEqual(test.status_code, HTTP_ACCEPTED)
        self.assertIsNotNone(server.userdata[self.active_user].get('reset_code'))

    def test_pending_user(self):
        url = SERVER_API + 'users/{}/reset'.format(self.pending_user)
        new_password = pick_rand_pw(10)
        previous_pending_activation = server.pending_users[self.pending_user]['activation_code']
        previous_pending_timestamp = server.pending_users[self.pending_user]['timestamp']

        # TODO: remove this block of sleep when timestamp is multiplied by 10,000 and converted to integer
        # Wait at least 1 second (temporary! because of 'now_timestamp' "1-second-level truncation")
        import time
        time.sleep(1.1)
        # end of sleep block

        test = self.app.post(url,
                             data={'password': new_password})
        self.assertEqual(test.status_code, HTTP_ACCEPTED)
        self.assertNotEqual(previous_pending_activation,
                            server.pending_users[self.pending_user]['activation_code'])
        self.assertLess(previous_pending_timestamp,
                        server.pending_users[self.pending_user]['timestamp'])

    def test_unknow_user(self):
        url = SERVER_API + 'users/{}/reset'.format('unknown@pippo.it')
        test = self.app.post(url,
                             data={'password': 'okokokoko'})
        self.assertEqual(test.status_code, HTTP_NOT_FOUND)

    def test_put(self):
        old_password = server.userdata[self.active_user]['password']
        # first request a new password with post
        self.app.post(SERVER_API + 'users/{}/reset'.format(self.active_user))
        reset_code = server.userdata[self.active_user]['reset_code']
        # then, put with given code and new password
        test = self.app.put(SERVER_API + 'users/{}'.format(self.active_user),
                            data={'reset_code': reset_code,
                                  'password': pick_rand_pw(10)})
        self.assertEqual(test.status_code, HTTP_OK)
        self.assertNotEqual(old_password, server.userdata[self.active_user]['password'])


def get_dic_dir_states():
    """
    Return a tuple with dictionary state and directory state of all users.
    NB: Passwords are removed from the dictionary states.
    :return: tuple
    """
    dic_state = {}
    dir_state = {}
    for username in server.userdata:
        single_user_data = server.userdata[username].copy()
        single_user_data.pop(server.PWD)  # not very beautiful
        single_user_data.pop(server.USER_CREATION_TIME)  # not very beautiful
        dic_state[username] = single_user_data
        dir_state = json.load(open('userdata.json', "rb"))
        dir_state[username].pop(server.PWD) # not very beatiful cit. ibidem
        dir_state[username].pop(server.USER_CREATION_TIME) # not very beatiful cit. ibidem
    return dic_state, dir_state


class TestUserdataConsistence(unittest.TestCase):
    """
    Testing consistence between userdata dictionary and actual files.
    """

    def setUp(self):
        setup_test_dir()
        self.app = server.app.test_client()
        self.app.testing = True

    def test_consistence_after_actions(self):
        """
        Complex test that do several actions and finally test the consistency.
        """
        # create user
        user = 'pippo'
        _manually_create_user(user, 'pass')

        # i need to create the userdata.json to check consistency
        server.save_userdata()

        # post
        _create_file(user, 'new_file', 'ciao!!!')
        url = SERVER_FILES_API + 'new_file'
        self.app.post(url, headers=make_basicauth_headers(USR, PW))

        # move
        move_test_url = SERVER_ACTIONS_API + 'move'
        src_move_test_file_path = 'test_move_src/testmovesrc.txt'
        dst_move_test_file_path = 'test_move_dst/testmovedst.txt'
        # create source file to be moved and its destination
        _create_file(user, src_move_test_file_path, 'this is the file to be moved')
        test = self.app.post(move_test_url,
                             headers=make_basicauth_headers(user, 'pass'),
                             data={'src': src_move_test_file_path, 'dst': dst_move_test_file_path},
                             follow_redirects=True)

        # copy
        copy_test_url = SERVER_FILES_API + 'copy'
        test = self.app.post(copy_test_url,
                             headers=make_basicauth_headers(user, 'pass'),
                             data={'src': src_move_test_file_path, 'dst': dst_move_test_file_path},
                             follow_redirects=True)

        # intermediate check
        dic_state, dir_state = get_dic_dir_states()
        self.assertEqual(dic_state, dir_state)


        user, pw = 'pippo', 'pass'
        # delete new_file
        delete_test_url = SERVER_ACTIONS_API + 'delete'
        self.app.post(delete_test_url,
                      headers=make_basicauth_headers(user, pw),
                      data={'filepath': "new_file"})
        # check consistency
        dic_state, dir_state = get_dic_dir_states()
        self.assertEqual(dic_state, dir_state)
        # WIP: Test not complete. TODO: Do more things! Put, ...?


class TestLoggingConfiguration(unittest.TestCase):
    """
    Testing log directory creation if it doesn't exists
    """

    def setUp(self):
        if os.path.isdir('log'):
            shutil.rmtree('log')

    def test_create_log_directory(self):
        self.assertFalse(os.path.exists('log') and os.path.isdir('log'))
        reload(server)
        self.assertTrue(os.path.exists('log') and os.path.isdir('log'))


if __name__ == '__main__':
    unittest.main()
