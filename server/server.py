# !/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
import shutil
import logging
import datetime
import argparse
import hashlib
join = os.path.join
import time

from flask import Flask, make_response, request, abort, jsonify
from flask.ext.httpauth import HTTPBasicAuth
from flask.ext.restful import Resource, Api
from werkzeug import secure_filename
from passlib.hash import sha256_crypt

__title__ = 'PyBOX'

# HTTP STATUS CODES
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_ACCEPTED = 202
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409

FILE_ROOT = 'filestorage'

URL_PREFIX = '/API/V1'
WORKDIR = os.path.dirname(__file__)
# Users login data are stored in a json file in the server
USERDATA_FILENAME = 'userdata.json'
# json key to access to the user directory snapshot:
SNAPSHOT = 'files'
LAST_SERVER_TIMESTAMP = 'server_timestamp'
PASSWORD = 'password'
DEFAULT_USER_DIRS = ('Misc', 'Music', 'Photos', 'Projects', 'Work')


# Logging configuration
# =====================
LOG_FILENAME = 'log/server.log'
if not os.path.isdir('log'):
    os.mkdir('log')

logger = logging.getLogger('Server log')
# Set the default logging level, actually used if the module is imported:
logger.setLevel(logging.WARN)

# It's useful to log all messages of all severities to a text file while simultaneously
# logging errors or above to the console. You set this up simply configuring the appropriate handlers.
# Create file handler which logs even debug messages:
file_handler = logging.FileHandler(LOG_FILENAME)
file_handler.setLevel(logging.DEBUG)
# Create console handler with a higher log level:
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)  # changeable from command line passing verbosity option or --verbose or --debug
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# First log message
launched_or_imported = {True: 'launched', False: 'imported'}[__name__ == '__main__']
logger.info('-' * 79)
logger.info('Server {} at {}'.format(launched_or_imported, datetime.datetime.now().isoformat(' ')))

# Server initialization
# =====================
userdata = {}

app = Flask(__name__)
api = Api(app)
auth = HTTPBasicAuth()


def _read_file(filename):
    """
    This function reads and returns the content of the file.
    """
    with open(filename, 'rb') as f:
        content = f.read()
    return content


def now_timestamp():
    """
    Return the current server timestamp as an int.
    :return: int
    """
    return int(time.time())


def file_timestamp(filepath):
    """
    Return the int of last modification timestamp of <filepath> (i.e. int(os.path.getmtime(filepath))).

    :param filepath: str
    :return: int
    """
    return int(os.path.getmtime(filepath))


def _encrypt_password(password):
    """
    Return the password encrypted as a string.
    :rtype : str
    """
    return sha256_crypt.encrypt(password)


def init_root_structure():
    """
    Create the file root directory if needed.
    :return: int
    """
    if not os.path.isdir(FILE_ROOT):
        os.mkdir(FILE_ROOT)
        return 1
    else:
        return 0


def init_user_directory(username, default_dirs=DEFAULT_USER_DIRS):
    """
    Create the default user directory.
    :param username: str
    :param default_dirs: tuple
    """
    dirpath = join(FILE_ROOT, username)
    if os.path.isdir(dirpath):
        shutil.rmtree(dirpath)
        logger.info('"{}" directory removed'.format(dirpath))
    os.makedirs(dirpath)

    welcome_file = join(dirpath, 'WELCOME')
    with open(welcome_file, 'w') as fp:
        fp.write('Welcome to %s, %s!\n' % (__title__, username))
    last_timestamp = file_timestamp(welcome_file)

    for dirname in default_dirs:
        subdirpath = join(dirpath, dirname)
        filepath = join(subdirpath, '{}.txt'.format(dirname))
        os.mkdir(subdirpath)
        # Create a default file for each default directory
        # beacuse wee need files to see the directories.
        with open(filepath, 'w') as fp:
            fp.write('{} {}\n'.format(username, dirname))
        last_timestamp = file_timestamp(filepath)
    logger.info('{} created'.format(dirpath))
    return last_timestamp, calculate_dir_snapshot(dirpath)


def load_userdata():
    data = {}
    try:
        with open(USERDATA_FILENAME, 'rb') as fp:
            data = json.load(fp, 'utf-8')
    except IOError:
        # If the user data file does not exists, don't raise an exception.
        # (the file will be created with the first user creation)
        pass
    logger.debug('Registered user(s): {}'.format(', '.join(data.keys())))
    logger.info('{:,} registered user(s) found'.format(len(data)))
    return data


def save_userdata(data):
    with open(USERDATA_FILENAME, 'wb') as fp:
        json.dump(data, fp, 'utf-8')
    logger.info('Saved {:,} users'.format(len(data)))


@auth.verify_password
def verify_password(username, password):
    """
    We redefine this function to check password with the encrypted one.
    """
    if not username:
        # Warning/info?
        return False
    single_user_data = userdata.get(username)
    if single_user_data:
        stored_pw = single_user_data.get(PASSWORD)
        assert stored_pw is not None, 'Server error: user data must contain a password!'
        res = sha256_crypt.verify(password, stored_pw)
    else:
        logger.info('User "{}" does not exist'.format(username))
        res = False
    return res


@app.route('{}/signup'.format(URL_PREFIX), methods=['POST'])
def create_user():
    """
    Handle the creation of a new user.
    """
    # Example of creation using requests:
    # requests.post('http://127.0.0.1:5000/API/V1/signup',
    #               data={'username': 'Pippo', 'password': 'ciao'})
    logger.debug('Creating user...')
    username = request.form.get('username')
    password = request.form.get('password')
    if username and password:
        if username in userdata:
            # user already exists!
            response = 'Error: username "{}" already exists!\n'.format(username), HTTP_CONFLICT
        else:
            enc_pass = _encrypt_password(password)
            last_server_timestamp, dir_snapshot = init_user_directory(username)
            single_user_data = {PASSWORD: enc_pass,
                                LAST_SERVER_TIMESTAMP: last_server_timestamp,
                                SNAPSHOT: dir_snapshot}
            userdata[username] = single_user_data
            save_userdata(userdata)
            response = 'User "{}" created.\n'.format(username), HTTP_CREATED
    else:
        response = 'Error: username or password is missing.\n', HTTP_BAD_REQUEST
    logger.debug(response)
    return response


class Actions(Resource):
    @auth.login_required
    def post(self, cmd):
        username = auth.username()
        methods = {'delete': self._delete,
                   'copy': self._copy,
                   'move': self._move,
                   }
        if methods:
            methods.get(cmd)(username)
        else:
            abort(HTTP_NOT_FOUND)

    def _get_src_dst(self, username):
        """
        Get the source and destination paths to complete _move and _copy actions.
        Controls if both source and destination are in real_root (http://~.../actions/<cmd>) and
        returns the absolute paths of them
        """
        src = request.form['src']
        dst = request.form['dst']
        src_path = os.path.abspath(join(FILE_ROOT, username, src))
        dst_path = os.path.abspath(join(FILE_ROOT, username, dst))
        real_root = os.path.realpath(join(FILE_ROOT, username))

        if real_root not in src_path and real_root not in dst_path:
            abort(HTTP_FORBIDDEN)

        return src_path, dst_path

    def _delete(self, username):
        """
        Delete a file for a given <filepath>, and return the current server timestamp in a json.
        json format: {LAST_SERVER_TIMESTAMP: int}
        """
        filepath = request.form['filepath']
        rootpath = join(FILE_ROOT, username, filepath)
        filepath = os.path.abspath(rootpath)
        real_root = os.path.realpath(join(FILE_ROOT, username))

        if not os.path.isfile(filepath):
            abort(HTTP_NOT_FOUND)

        if real_root not in filepath:
            abort(HTTP_FORBIDDEN)

        try:
            os.remove(filepath)
        except OSError:
            abort(HTTP_NOT_FOUND)
        self._clear_dirs(os.path.dirname(filepath), username)
        # I deleted a file, so the last server timestamp is the current timestamp
        return jsonify({LAST_SERVER_TIMESTAMP: now_timestamp()})

    def _copy(self, username):
        """
        Copy a file from a given source path to a destination path and return the current server timestamp in a json.
        json format: {LAST_SERVER_TIMESTAMP: int}
        """
        src_path, dst_path = self._get_src_dst(username)

        if os.path.isfile(src_path):
            if not os.path.exists(os.path.dirname(dst_path)):
                os.makedirs(os.path.dirname(dst_path))
            shutil.copy(src_path, dst_path)
        else:
            abort(HTTP_NOT_FOUND)
        # TODO: return dst file timestamp instead of current timestamp?
        return jsonify({LAST_SERVER_TIMESTAMP: now_timestamp()})

    def _move(self, username):
        """
        Move a file from a given source path to a destination path, and return the current server timestamp in a json.
        json format: {LAST_SERVER_TIMESTAMP: int}
        """
        src_path, dst_path = self._get_src_dst(username)

        if os.path.isfile(src_path):
            if not os.path.exists(os.path.dirname(dst_path)):
                os.makedirs(os.path.dirname(dst_path))
            shutil.move(src_path, dst_path)
        else:
            abort(HTTP_NOT_FOUND)
        self._clear_dirs(os.path.dirname(src_path), username)
        # TODO: return dst file timestamp instead of current timestamp?
        return jsonify({LAST_SERVER_TIMESTAMP: now_timestamp()})

    def _clear_dirs(self, path, root):
        """
        Recursively removes all the empty directories that exists after the remotion of a file
        """

        path_to_clear, clean = os.path.split(path)
        path_to_storage, storage = os.path.split(path_to_clear)
        if clean == root and storage == FILE_ROOT:
            return
        try:
            os.rmdir(path)
        except OSError:
            return
        self._clear_dirs(path_to_clear, root)


def calculate_file_md5(fp, chunk_len=2 ** 16):
    """
    Return the md5 digest of the file content of file_path as a string
    with only hexadecimal digits.
    :fp: file (an open file object)
    :chunk_len: int (number of file bytes read per cycle - default = 2^16)
    """
    h = hashlib.md5()
    while True:
        chunk = fp.read(chunk_len)
        if chunk:
            h.update(chunk)
        else:
            break
    res = h.hexdigest()
    return res


def calculate_dir_snapshot(root_path):
    """
    Walk on root_path returning a snapshot in a dict.
    :param root_path: str
    :return: tuple
    """
    result = {}
    last_timestamp = 0
    for dirpath, dirs, files in os.walk(root_path):
        for filename in files:
            filepath = join(dirpath, filename)

            # Open file and calculate md5.
            try:
                with open(filepath, 'rb') as fp:
                    md5 = calculate_file_md5(fp)
            except OSError as err:
                logging.warn('calculate_file_md5("{}") --> {}'.format(filepath, err))
            else:
                timestamp = file_timestamp(filepath)
                if timestamp > last_timestamp:
                    last_timestamp = timestamp
                result[filepath[len(root_path) + 1:]] = [timestamp, md5]
    return last_timestamp, result


class Files(Resource):
    """
    Class that handle files as web resources.
    """
    @auth.login_required
    def get(self, path=''):
        """
        Download an authenticated user file from server, if <path> is not empty,
        otherwise get a server snapshot of user directory.
        <path> is the path relative to the user local directory.
        :param path: str
        """
        logger.debug('Files.get({})'.format(repr(path)))
        username = auth.username()
        user_rootpath = join(FILE_ROOT, username)
        if path:
            # Download the file specified by <path>.
            dirname = join(user_rootpath, os.path.dirname(path))
            real_dirname = os.path.realpath(dirname)
            real_root = os.path.realpath(join(FILE_ROOT, username))

            if real_root not in real_dirname:
                abort(HTTP_FORBIDDEN)
            if not os.path.exists(dirname):
                abort(HTTP_NOT_FOUND)
            s_filename = secure_filename(os.path.split(path)[-1])

            try:
                response = make_response(_read_file(join(FILE_ROOT, username, path)))
            except IOError:
                response = 'Error: file {} not found.\n'.format(path), HTTP_NOT_FOUND
            else:
                response.headers['Content-Disposition'] = 'attachment; filename=%s' % s_filename
        else:
            # If path is not given, return the snapshot of user directory.
            logger.debug('launch snapshot of {}...'.format(repr(user_rootpath)))
            last_server_timestamp, snapshot = calculate_dir_snapshot(user_rootpath)
            logger.info('snapshot returned {:,} files'.format(len(snapshot)))
            response = jsonify({LAST_SERVER_TIMESTAMP: last_server_timestamp,
                                SNAPSHOT: snapshot})
        logging.debug(response)
        return response

    @auth.login_required
    def _get_dirname_filename(self, path):
        """
        Return dirname(directory name) and filename(file name) for a given path to complete
        post and put methods
        """
        username = auth.username()
        dirname = os.path.dirname(path)
        dirname = (join(FILE_ROOT, username, dirname))
        real_dirname = os.path.realpath(dirname)
        real_root = os.path.realpath(join(FILE_ROOT, username))
        filename = os.path.split(path)[-1]

        if real_root not in real_dirname:
            abort(HTTP_FORBIDDEN)

        return dirname, filename

    @auth.login_required
    def post(self, path):
        """
        Upload an authenticated user file to the server, given the path relative to the user directory.
        Return the file timestamp of the file created in the server.
        The file must not exist in the server, otherwise only return an http forbidden code.
        :param path: str
        """
        upload_file = request.files['file']
        dirname, filename = self._get_dirname_filename(path)

        if not os.path.exists(dirname):
            os.makedirs(dirname)
        else:
            if os.path.isfile(join(dirname, filename)):
                abort(HTTP_FORBIDDEN)
        filepath = join(dirname, filename)
        upload_file.save(filepath)
        resp = jsonify({LAST_SERVER_TIMESTAMP: file_timestamp(filepath)})
        resp.status_code = HTTP_CREATED
        return resp

    @auth.login_required
    def put(self, path):
        """
        Modify an authenticated user file in the server (uploading and overwriting it)
        given the path relative to the user directory. The file must exist in the server.
        Return the file timestamp of the file updated in the server.
        :param path: str
        """
        upload_file = request.files['file']
        dirname, filename = self._get_dirname_filename(path)
        server_path = join(dirname, filename)

        if os.path.isfile(server_path):
            upload_file.save(server_path)
        else:
            abort(HTTP_NOT_FOUND)
        resp = jsonify({LAST_SERVER_TIMESTAMP: file_timestamp(server_path)})
        resp.status_code = HTTP_CREATED
        return resp


api.add_resource(Files, '{}/files/<path:path>'.format(URL_PREFIX), '{}/files/'.format(URL_PREFIX))
api.add_resource(Actions, '{}/actions/<string:cmd>'.format(URL_PREFIX))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', default=False, action='store_true',
                        help='set console verbosity level to DEBUG (4) [default: %(default)s]')
    parser.add_argument('--verbose', default=False, action='store_true',
                        help='set console verbosity level to INFO (3) [default: %(default)s]. \
                        Ignored if --debug option is set.')
    parser.add_argument('-v', '--verbosity', const=1, default=1, type=int, nargs='?',
                        help='set console verbosity: 0=CRITICAL, 1=ERROR, 2=WARN, 3=INFO, 4=DEBUG. \
                        [default: %(default)s]. Ignored if --verbose or --debug option is set.')
    parser.add_argument('-H', '--host', default='0.0.0.0', help='set host address to run the server. [default: %(default)s].')
    args = parser.parse_args()

    if args.debug:
        # If set to True, win against verbosity and verbose parameter
        console_handler.setLevel(logging.DEBUG)
    elif args.verbose:
        # If set to True, win against verbosity parameter
        console_handler.setLevel(logging.INFO)
    else:
        if args.verbosity == 0:  # Only show critical error message (very quiet)
            console_handler.setLevel(logging.CRITICAL)
        if args.verbosity == 1:  # Only show error message (quite quiet)
            console_handler.setLevel(logging.ERROR)
        elif args.verbosity == 2:  # Show only warning and error messages
            console_handler.setLevel(logging.WARNING)
        elif args.verbosity == 3:  # Verbose: show all messages except the debug ones
            console_handler.setLevel(logging.INFO)
        elif args.verbosity == 4:  # Show *all* messages
            console_handler.setLevel(logging.DEBUG)

    logger.debug('File logging level: {}'.format(file_handler.level))

    userdata.update(load_userdata())
    init_root_structure()
    app.run(host=args.host, debug=args.debug)

if __name__ == '__main__':
    main()
