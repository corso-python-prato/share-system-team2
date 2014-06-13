# !/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
import shutil
import logging
import datetime
import argparse
import hashlib

from flask import Flask, make_response, request, abort, jsonify
from flask.ext.httpauth import HTTPBasicAuth
from flask.ext.restful import Resource, Api
from werkzeug import secure_filename
from passlib.hash import sha256_crypt


# HTTP STATUS CODES
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_ACCEPTED = 202
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
FILE_ROOT = 'filestorage'

URL_PREFIX = '/API/V1'
WORKDIR = os.path.dirname(__file__)
# Users login data are stored in a json file in the server
USERDATA_FILENAME = 'userdata.json'
# json key to access to the user directory snapshot:
SNAPSHOT = 'files'
# Single file dict keys:
FILEPATH = 'filepath'
MTIME = 'mtime'
MD5 = 'md5'


# Logging configuration
# =====================
LOG_FILENAME = 'log/server.log'
if not os.path.isdir('log'):
    os.mkdir('log')

logger = logging.getLogger('Server log')
logger.setLevel(logging.DEBUG)
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


def _path(*relpath):
    """
    Build the path under WORKDIR.
    :param relpath:
    :return:
    """
    return os.path.join(WORKDIR, *relpath)


def _read_file(filename):
    """
    This function reads and returns the content of the file.
    """
    with open(filename, 'rb') as f:
        content = f.read()
    return content


def _encrypt_password(password):
    """
    Return the password encrypted as a string.
    :rtype : str
    """
    return sha256_crypt.encrypt(password)


def load_userdata():
    data = {}
    try:
        with open(_path(USERDATA_FILENAME), 'rb') as fp:
            data = json.load(fp, 'utf-8')
    except IOError:
        # If the user data file does not exists, don't raise an exception.
        # (the file will be created with the first user creation)
        pass
    logger.debug('Registered user(s): {}'.format(', '.join(data.keys())))
    logger.info('{:,} registered user(s) found'.format(len(data)))
    return data


def save_userdata(data):
    with open(_path(USERDATA_FILENAME), 'wb') as fp:
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
    stored_pw = userdata.get(username)
    if stored_pw:
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
            response = 'Error: username already exists!', HTTP_FORBIDDEN
        else:
            userdata[username] = _encrypt_password(password)
            response = 'User "{}" created'.format(username), HTTP_CREATED
            save_userdata(userdata)
            os.makedirs(os.path.join(FILE_ROOT, username))
    else:
        response = 'Error: username or password is missing', HTTP_BAD_REQUEST
    logger.debug(response)
    return response


class Actions(Resource):
    @auth.login_required
    def post(self, cmd):
        username = request.authorization['username']
        methods = {
        'delete': self._delete,
        'copy': self._copy,
        'move': self._move
        }
        if methods:
            methods.get(cmd)(username)
        else:
            abort(HTTP_NOT_FOUND)
    
    def _get_src_dst(self, username):
        """
        Gets the source and destination paths to complete _move and _copy actions.
        Controls if both source and destination are in real_root (http://~.../actions/<cmd>) and 
        returns the absolute paths of them
        """ 
        src = request.form['src']
        dst = request.form['dst']
        
        src_path = os.path.abspath(os.path.join(FILE_ROOT, username, src))
        dst_path = os.path.abspath(os.path.join(FILE_ROOT, username, dst))
        real_root = os.path.realpath(os.path.join(FILE_ROOT, username))
        
        if real_root not in src_path and real_root not in dst_path:
            abort(HTTP_FORBIDDEN)

        return src_path, dst_path               

    def _delete(self, username):
        """
        Delete a file for a given <filepath>
        """
        filepath = request.form['filepath']
        filepath = os.path.abspath(os.path.join(FILE_ROOT, username, filepath))

        if not os.path.isfile(filepath):
            abort(HTTP_NOT_FOUND)
        try:
            os.remove(filepath)
        except OSError:
            abort(HTTP_NOT_FOUND)

        self._clear_dirs(os.path.dirname(filepath), username)
            
    def _copy(self, username):
        """
        Copy a file from a given source path to a destination path
        """
        src_path, dst_path = self._get_src_dst(username)

        if os.path.isfile(src_path):
            if not os.path.exists(os.path.dirname(dst_path)):
                os.makedirs(os.path.dirname(dst_path))
            shutil.copy(src_path, dst_path)        
        else:
            abort(HTTP_NOT_FOUND)

    def _move(self, username):
        """
        Move a file from a given source path to a destination path
        """
        src_path, dst_path = self._get_src_dst(username)
        
        if os.path.isfile(src_path):
            if not os.path.exists(os.path.dirname(dst_path)):
                os.makedirs(os.path.dirname(dst_path))
            shutil.move(src_path, dst_path)        
        else:
            abort(HTTP_NOT_FOUND)
        self._clear_dirs(os.path.dirname(src_path), username)    

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


def calculate_file_md5(fp, chunk_len=2**16):
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


def dir_snapshot(root_path):
    """
    Walk on root_path returning a snapshot in a list of dictionaries.
    Every dict has FILEPATH, MTIME, MD5 keys.
    :param root_path: str
    :return: list

    >>> snap = dir_snapshot('.')
    >>> isinstance(snap, list)
    True
    >>> d = snap[0]
    >>> isinstance(d, dict)
    True
    >>> FILEPATH in d
    True
    >>> MTIME in d
    True
    >>> MD5 in d
    True
    >>> d[FILEPATH].__class__.__name__
    'str'
    >>> d[MTIME].__class__.__name__
    'float'
    >>> d[MD5].__class__.__name__
    'str'
    >>> os.path.exists(d[FILEPATH])
    True
    """
    res = []
    for dirpath, dirs, files in os.walk(root_path):
        for filename in files:
            filepath = os.path.join(dirpath, filename)
            lastmod_timestamp = os.path.getmtime(filepath)

            # Open file and calculate md5. TODO: catch and handle os errors.
            with open(filepath, 'rb') as fp:
                md5_string = calculate_file_md5(fp)

            # dict info for each file (we could use a tuple)
            d = {
                 FILEPATH: filepath[len(root_path) + 1:],
                 MTIME: lastmod_timestamp,
                 MD5: md5_string,
            }
            res.append(d)
    return res


class Files(Resource):
    @auth.login_required
    def get(self, path=''):
        logger.debug('Files.get({})'.format(repr(path)))
        username = request.authorization['username']
        user_rootpath = os.path.join(FILE_ROOT, username)
        if path:
            # Download the file specified by <path>.
            dirname = os.path.join(user_rootpath, os.path.dirname(path))
            real_dirname = os.path.realpath(dirname)
            real_root = os.path.realpath(os.path.join(FILE_ROOT, username))

            if real_root not in real_dirname:
                abort(HTTP_FORBIDDEN)
            if not os.path.exists(dirname):
                abort(HTTP_NOT_FOUND)
            s_filename = secure_filename(os.path.split(path)[-1])

            try:
                response = make_response(_read_file(os.path.join(FILE_ROOT, username, path)))
            except IOError:
                response = 'File not found', HTTP_NOT_FOUND
            else:
                response.headers['Content-Disposition'] = 'attachment; filename=%s' % s_filename
        else:
            # If path is not given, return the snapshot of user directory.
            logger.debug('launch snapshot of {}...'.format(repr(user_rootpath)))
            snapshot = dir_snapshot(user_rootpath)
            logger.info('snapshot returned {:,} files'.format(len(snapshot)))
            response = jsonify({SNAPSHOT: snapshot})
        logging.debug(response)
        return response

    @auth.login_required
    def post(self, path):
        username = request.authorization['username']
        upload_file = request.files['file']
        dirname = os.path.dirname(path)
        dirname = (os.path.join(FILE_ROOT, username, dirname))
        real_dirname = os.path.realpath(dirname)
        real_root = os.path.realpath(os.path.join(FILE_ROOT, username))
        filename = os.path.split(path)[-1]

        if real_root not in real_dirname:
            abort(HTTP_FORBIDDEN)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        else:
            if os.path.isfile(os.path.join(dirname, filename)):
                abort(HTTP_FORBIDDEN)
        upload_file.save(os.path.join(dirname, filename))
        return '', HTTP_CREATED

    @auth.login_required
    def put(self, path):
        username = request.authorization['username']
        upload_file = request.files['file']
        dirname = os.path.dirname(path)
        dirname = (os.path.join(FILE_ROOT, username, dirname))
        real_dirname = os.path.realpath(dirname)
        real_root = os.path.realpath(os.path.join(FILE_ROOT, username))
        filename = os.path.split(path)[-1]

        if real_root not in real_dirname:
            abort(HTTP_FORBIDDEN)
        if os.path.isfile(os.path.join(dirname, filename)):
           upload_file.save(os.path.join(dirname, filename))
           return '', HTTP_CREATED
        else:
            abort(HTTP_NOT_FOUND)


api.add_resource(Files, '{}/files/<path:path>'.format(URL_PREFIX), '{}/files/'.format(URL_PREFIX))
api.add_resource(Actions, '{}/actions/<string:cmd>'.format(URL_PREFIX))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', default=False, action='store_true',
                        help='set console verbosity level to DEBUG (4) [default: %(default)s]')
    parser.add_argument('--verbose', default=False, action='store_true',
                        help='set console verbosity level to INFO (3) [default: %(default)s]. \
                        Ignored if --debug option is set.')
    parser.add_argument('-v', '--verbosity', const=1, default=1, type=int, nargs='?',
                        help='set console verbosity: 0=CRITICAL, 1=ERROR, 2=WARN, 3=INFO, 4=DEBUG. \
                        [default: %(default)s]. Ignored if --verbose or --debug option is set.')
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
    app.run(host='0.0.0.0', debug=True)
