#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ConfigParser
import os
import json
import shutil
import logging
import datetime
import argparse
import hashlib
import time
import string

join = os.path.join
normpath = os.path.normpath
abspath = os.path.abspath

from flask import Flask, make_response, request, abort, jsonify
from flask.ext.httpauth import HTTPBasicAuth
from flask.ext.restful import Resource, Api
from flask.ext.mail import Mail, Message
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

USER_ACTIVATION_TIMEOUT = 60 * 60 * 24 * 3  # expires after 3 days

# json key to access to the user directory snapshot:
SNAPSHOT = 'files'
LAST_SERVER_TIMESTAMP = 'server_timestamp'
PWD = 'password'
USER_CREATION_TIME = 'creation_timestamp'
DEFAULT_USER_DIRS = ('Misc', 'Music', 'Photos', 'Projects', 'Work')


class ServerError(Exception):
    pass


class ServerConfigurationError(ServerError):
    pass


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
pending_users = {}

app = Flask(__name__)
app.testing = __name__ != '__main__'  # Reasonable assumption?
# if True, you can see the exception traceback, suppress the sending of emails, etc.
EMAIL_SETTINGS_FILEPATH = join(os.path.dirname(__file__),
                               ('email_settings.ini', 'email_settings.ini.example')[app.testing])

api = Api(app)
auth = HTTPBasicAuth()


def _read_file(filename):
    """
    This function reads and returns the content of the file.
    """
    with open(filename, 'rb') as f:
        content = f.read()
    return content


def check_path(path, username):
    """
    Check that a path don't fall in other user directories or upper.
    Examples:

    >>> check_path('Photos/myphoto.jpg', 'pippo')
    True
    >>> check_path('Photos/../../ciao.txt', 'paperino')
    False
    """
    path = os.path.abspath(join(FILE_ROOT, username, path))
    root = os.path.abspath(join(FILE_ROOT, username))
    if root in path:
        return True
    return False


def userpath2serverpath(username, path=''):
    """
    Given an username and its relative path, return the
    corresponding path in the server. If the path is empty,
    return the user path directory in the server.
    :param username: str
    :param path: str
    :return: str
    """
    return os.path.realpath(os.path.join(FILE_ROOT, username, path))


def now_timestamp():
    """
    Return the current server timestamp as an int.
    :return: long
    """
    return long(time.time()*10000)


def file_timestamp(filepath):
    """
    Return the long of last modification timestamp of <filepath> (i.e. long(os.path.getmtime(filepath))).

    :param filepath: str
    :return: long
    """

    return long(os.path.getmtime(filepath)*10000)


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
    :param default_dirs: dict
    """
    dirpath = join(FILE_ROOT, username)
    if os.path.isdir(dirpath):
        shutil.rmtree(dirpath)
        logger.info('"{}" directory removed'.format(dirpath))
    os.makedirs(dirpath)

    welcome_file = join(dirpath, 'WELCOME')
    with open(welcome_file, 'wb') as fp:
        fp.write('Welcome to %s, %s!\n' % (__title__, username))

    for dirname in default_dirs:
        subdirpath = join(dirpath, dirname)
        filepath = join(subdirpath, '{}.txt'.format(dirname))
        os.mkdir(subdirpath)
        # Create a default file for each default directory
        # beacuse wee need files to see the directories.
        with open(filepath, 'wb') as fp:
            fp.write('{} {}\n'.format(username, dirname))
    logger.info('{} created'.format(dirpath))
    return compute_dir_state(dirpath)


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


def save_userdata():
    """
    Save module level <userdata> dict to disk as json.
    :return: None
    """
    with open(USERDATA_FILENAME, 'wb') as fp:
        json.dump(userdata, fp, 'utf-8', indent=4)
    logger.info('Saved {:,} users'.format(len(userdata)))


def reset_userdata():
    """
    Clear userdata and pending_users dictionaries.
    """
    userdata.clear()
    pending_users.clear()


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
        stored_pw = single_user_data.get(PWD)
        assert stored_pw is not None, 'Server error: user data must contain a password!'
        res = sha256_crypt.verify(password, stored_pw)
    else:
        logger.info('User "{}" does not exist'.format(username))
        res = False
    return res


def create_user(username, password):
    """
    Handle the creation of a new user.
    """
    # Example of creation using requests:
    # requests.post('http://127.0.0.1:5000/API/V1/signup',
    # data={'username': 'Pippo', 'password': 'ciao'})
    logger.debug('Creating user...')
    if username and password:
        if username in userdata:
            # user already exists!
            response = 'Error: username "{}" already exists!\n'.format(username), HTTP_CONFLICT
        else:
            enc_pass = _encrypt_password(password)

            temp = init_user_directory(username)
            last_server_timestamp, dir_snapshot = temp[LAST_SERVER_TIMESTAMP], temp[SNAPSHOT]

            single_user_data = {USER_CREATION_TIME: now_timestamp(),
                                PWD: enc_pass,
                                LAST_SERVER_TIMESTAMP: last_server_timestamp,
                                SNAPSHOT: dir_snapshot,
                                }
            userdata[username] = single_user_data
            save_userdata()
            response = 'User "{}" created.\n'.format(username), HTTP_CREATED
    else:
        response = 'Error: username or password is missing.\n', HTTP_BAD_REQUEST
    logger.debug(response)
    return response


@app.route('{}/signup'.format(URL_PREFIX), methods=['POST'])
def signup():
    """
    Old simpler and immediate signup method (no mail) temporarily maintained only for testing purposes.
    """
    username = request.form.get('username')
    password = request.form.get('password')
    return create_user(username, password)


def configure_email():
    """
    Configure Flask Mail from the email_settings.ini in place. Return a flask.ext.mail.Mail instance.
    """
    # Relations between Flask configuration keys and settings file fields.
    keys_tuples = [
        ('MAIL_SERVER', 'smtp_address'),  # the address of the smtp server
        ('MAIL_PORT', 'smtp_port'),  # the port of the smtp server
        ('MAIL_USERNAME', 'smtp_username'),  # the username of the smtp server (if required)
        ('MAIL_PASSWORD', 'smtp_password'),  # the password of the smtp server (if required)
    ]

    cfg = ConfigParser.ConfigParser()
    cfg.read(EMAIL_SETTINGS_FILEPATH)
    for flask_key, file_key in keys_tuples:
        value = cfg.get('email', file_key)
        if flask_key == 'MAIL_PORT':
            value = int(value)
        app.config[flask_key] = value

    return Mail(app)


def send_email(subject, sender, recipients, text_body):
    """
    Sent an email and return the Message instance of sent email.

    :param subject: str
    :param sender: str
    :param recipients: list
    :param text_body: str
    :return: Message
    """
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    mail.send(msg)
    return msg


class UsersFacility(Resource):
    """
    Debug facility/backdoor to get all users (and pending users) info and without authentication.
    """

    def get(self, username):
        """
        Show some info about users.
        """
        if username == '__all__':
            # Easter egg to see a list of registered and pending users.
            if userdata:
                reg_users_listr = ', '.join(userdata.keys())
            else:
                reg_users_listr = 'no registered users'
            if pending_users:
                pending_users_listr = ', '.join(pending_users.keys())
            else:
                pending_users_listr = 'no pending users'
            response = 'Registered users: {}. Pending users: {}'.format(reg_users_listr, pending_users_listr), \
                       HTTP_OK
        else:
            if username in userdata:
                user_data = userdata[username]
                creation_timestamp = user_data.get(USER_CREATION_TIME)
                if creation_timestamp:
                    time_str = time.strftime('%Y-%m-%d at %H:%M:%S', time.localtime(creation_timestamp))
                else:
                    time_str = '<unknown time>'
                response = 'User {} joined on {}.'.format(username, time_str), HTTP_OK
            else:
                response = 'The user {} does not exist.'.format(username), HTTP_NOT_FOUND
        return response


class Users(Resource):
    def _clean_pending_users(self):
        """
        Remove expired pending users (users whose activation time is expired)
        and return a list of them.
        :return: list
        """
        # Remove expired pending users.
        to_remove = [username for (username, data) in pending_users.iteritems()
                     if now_timestamp() - data['timestamp'] > USER_ACTIVATION_TIMEOUT]
        [pending_users.pop(username) for username in to_remove]
        return to_remove

    @auth.login_required
    def get(self, username):
        """
        Show logged user details.
        """
        logged = auth.username()
        if username == logged:
            user_data = userdata[username]
            creation_timestamp = user_data.get(USER_CREATION_TIME)
            if creation_timestamp:
                time_str = time.strftime('%Y-%m-%d at %H:%M:%S', time.localtime(creation_timestamp/10000.0))
            else:
                time_str = '<unknown time>'
            # TODO: return json?
            response = 'You joined on {}.'.format(time_str), HTTP_OK
            return response
        else:
            abort(HTTP_FORBIDDEN)

    def post(self, username):
        """
        A not-logged user is asking to register himself.
        NB: username must be a valid email address.
        """
        if username in userdata:
            abort(HTTP_CONFLICT)

        password = request.form['password']

        activation_code = os.urandom(16).encode('hex')

        # Composing email
        subject = '[{}] Confirm your email address'.format(__title__)
        sender = 'donotreply@{}.com'.format(__title__)
        recipients = [username]
        text_body_template = string.Template("""
Thanks for signing up for $appname!

As a final step of the $appname account creation process, please confirm the email address $email.
Copy and paste the activation code below into the desktop application:

$code

If you don't know what this is about, then someone has probably entered your email address by mistake.
Sorry about that. You don't need to do anything further. Just delete this message.

Cheers,
the $appname Team
""")
        values = dict(code=activation_code,
                      email=username,
                      appname=__title__,
                      )
        text_body = text_body_template.substitute(values)

        send_email(subject, sender, recipients, text_body)

        pending_users[username] = {
            'timestamp': now_timestamp(),
            'activation_code': activation_code,
            PWD: password,
        }
        return 'User activation email sent to {}'.format(username), HTTP_OK

    def put(self, username):
        """
        Create user using activation code sent by email, or reset its password.
        """
        logger.debug('Pending users: {}'.format(pending_users.keys()))

        # Pending users cleanup
        expired_pending_users = self._clean_pending_users()
        logging.info('Expired pending users: {}'.format(expired_pending_users))

        if username in userdata:
            # The user is already active, so it should be a request of password resetting.
            if username in pending_users:
                raise RuntimeError('Programming error: user {} must\'n t be both pending and active'.format(username))
            try:
                new_password = request.form[PWD]
            except KeyError:
                abort(HTTP_BAD_REQUEST)
            else:
                request_recoverpass_code = request.form['recoverpass_code']
                recoverpass_code = userdata[username].get('recoverpass_code')
                if request_recoverpass_code == recoverpass_code:
                    userdata[PWD] = new_password
                    #print('Updating password with "{}"'.format(new_password))
                    enc_pass = _encrypt_password(new_password)
                    userdata[username][PWD] = enc_pass
                    userdata[username].pop('recoverpass_code')
                    response = 'Password changed succesfully', HTTP_OK
                else:
                    # reset code not corresponding
                    response = 'Code not corrisponding: {} vs {}'.format(recoverpass_code,
                                                                         request_recoverpass_code), HTTP_NOT_FOUND
                return response
        else:
            activation_code = request.form['activation_code']
            logger.debug('Got activation code: {}'.format(activation_code))
            print('no {} in userdata.keys() = {}'.format(username, userdata.keys()))
            pending_user_data = pending_users.get(username)
            if pending_user_data:
                logger.debug('Activating user {}'.format(username))
                if activation_code == pending_user_data['activation_code']:
                    # Actually create user
                    password = pending_user_data[PWD]
                    pending_users.pop(username)
                    return create_user(username, password)
                else:
                    abort(HTTP_NOT_FOUND)
            else:
                logger.info('{} is not pending'.format(username))
                abort(HTTP_NOT_FOUND)

    @auth.login_required
    def delete(self, username):
        """
        Delete all logged user's files and data.
        The same user won't more log in, but it can be recreated with the signup procedure.
        """
        logged = auth.username()

        if username != logged:
            # I mustn't delete other users!
            abort(HTTP_FORBIDDEN)

        userdata.pop(username)
        # TODO: add save_userdata()
        shutil.rmtree(userpath2serverpath(username))
        return 'User "{}" removed.\n'.format(username), HTTP_OK


class UsersReset(Resource):
    """
    This class handles the recovering of a lost user's password by changing it.

    Use case: the user has forgotten its password and wants to recover it.
    NB: recover the old password is not even possible since it's stored encrypted.
    """
    def post(self, username):
        """
        Handle the request for change the user's password
        by sending a 'recoverpass' token to its email address.
        """
        recoverpass_code = os.urandom(16).encode('hex')

        # The password reset must be called from an active or inactive user
        if not(username in userdata or username in pending_users):
            abort(HTTP_NOT_FOUND)

        # Composing email
        subject = '[{}] Password reset'.format(__title__)
        sender = 'donotreply@{}.com'.format(__title__)
        recipients = [username]
        text_body_template = string.Template("""
Hi there,

There was recently a request to change the password on your $email account.
If you requested this password change, please set a new password by following the link below:

$code

If you don't want to change your password, just ignore this message.

Cheers,
the $appname Team
""")
        values = dict(code=recoverpass_code,
                      email=username,
                      appname=__title__,
                      )
        text_body = text_body_template.substitute(values)

        send_email(subject, sender, recipients, text_body)

        if username in userdata:
            # create or update 'recoverpass_code' key. No expiration time.
            userdata[username]['recoverpass_code'] = recoverpass_code
        elif username in pending_users:
            pending_users[username] = {'timestamp': now_timestamp(),
                                       'activation_code': recoverpass_code}
        # the else case is already covered in the first if

        return 'Reset email sent to {}'.format(username), HTTP_ACCEPTED


class Actions(Resource):
    @auth.login_required
    def post(self, cmd):
        username = auth.username()
        methods = {'delete': self._delete,
                   'copy': self._copy,
                   'move': self._move,
                   }
        try:
            resp = methods[cmd](username)
        except KeyError:
            abort(HTTP_NOT_FOUND)
        else:
            save_userdata()
            return resp

    def _delete(self, username):
        """
        Delete a file for a given <filepath>, and return the current server timestamp in a json.
        json format: {LAST_SERVER_TIMESTAMP: int}
        """
        filepath = request.form['filepath']

        if not check_path(filepath, username):
            abort(HTTP_FORBIDDEN)

        abspath = os.path.abspath(join(FILE_ROOT, username, filepath))

        try:
            os.remove(abspath)
        except OSError:
            # This error raises when the file is missing
            abort(HTTP_NOT_FOUND)
        self._clear_dirs(os.path.dirname(abspath), username)

        # file deleted, last_server_timestamp is set to current timestamp
        last_server_timestamp = now_timestamp()
        userdata[username][LAST_SERVER_TIMESTAMP] = last_server_timestamp
        userdata[username]['files'].pop(normpath(filepath))
        save_userdata()
        return jsonify({LAST_SERVER_TIMESTAMP: last_server_timestamp})

    def _copy(self, username):
        """
        Copy a file from a given source path to a destination path and return the current server timestamp in a json file.
        jso
        userdata[username]n format: {LAST_SERVER_TIMESTAMP: int}
        """

        src = request.form['src']
        dst = request.form['dst']
        server_src = userpath2serverpath(username, src)
        server_dst = userpath2serverpath(username, dst)

        if not (check_path(src, username) or check_path(dst, username)):
            abort(HTTP_FORBIDDEN)

        if os.path.isfile(server_src):
            if not os.path.exists(os.path.dirname(server_dst)):
                os.makedirs(os.path.dirname(server_dst))
            shutil.copy(server_src, server_dst)
        else:
            abort(HTTP_NOT_FOUND)

        last_server_timestamp = file_timestamp(server_dst)

        _, md5 = userdata[username]['files'][normpath(src)]
        userdata[username][LAST_SERVER_TIMESTAMP] = last_server_timestamp
        userdata[username]['files'][normpath(dst)] = [last_server_timestamp, md5]
        save_userdata()
        return jsonify({LAST_SERVER_TIMESTAMP: last_server_timestamp})

    def _move(self, username):
        """
        Move a file from a given source path to a destination path, and return the current server timestamp in a json.
        json format: {LAST_SERVER_TIMESTAMP: int}
        """
        src = request.form['src']
        dst = request.form['dst']
        server_src = userpath2serverpath(username, src)
        server_dst = userpath2serverpath(username, dst)

        if not (check_path(src, username) or check_path(dst, username)):
            abort(HTTP_FORBIDDEN)

        if os.path.isfile(server_src):
            if not os.path.exists(os.path.dirname(server_dst)):
                os.makedirs(os.path.dirname(server_dst))
            shutil.move(server_src, server_dst)
        else:
            abort(HTTP_NOT_FOUND)
        self._clear_dirs(os.path.dirname(server_src), username)


        last_server_timestamp = now_timestamp()

        _, md5 = userdata[username]['files'][normpath(src)]
        userdata[username][LAST_SERVER_TIMESTAMP] = last_server_timestamp
        userdata[username]['files'].pop(normpath(src))
        userdata[username]['files'][normpath(dst)] = [last_server_timestamp, md5]
        save_userdata()
        return jsonify({LAST_SERVER_TIMESTAMP: last_server_timestamp})

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


def compute_dir_state(root_path):  # TODO: make function accepting just an username instead of an user root_path.
    """
    Walk on root_path returning the directory snapshot in a dict (dict keys are identified by this 2 constants:
    LAST_SERVER_TIMESTAMP and SNAPSHOT)

    :param root_path: str
    :return: dict.
    """
    snapshot = {}
    last_timestamp = now_timestamp()
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
                snapshot[filepath[len(root_path) + 1:]] = [last_timestamp, md5]
    state = {LAST_SERVER_TIMESTAMP: last_timestamp,
             SNAPSHOT: snapshot}
    return state


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

            if not check_path(path, username):
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
            snapshot = userdata[username][SNAPSHOT]
            logger.info('snapshot returned {:,} files'.format(len(snapshot)))
            last_server_timestamp = userdata[username][LAST_SERVER_TIMESTAMP]
            response = jsonify({LAST_SERVER_TIMESTAMP: last_server_timestamp,
                                SNAPSHOT: snapshot})
        logging.debug(response)
        return response

    def _get_dirname_filename(self, path):
        """
        Return dirname(directory name) and filename(file name) for a given path to complete
        post and put methods
        """
        username = auth.username()
        dirname = os.path.dirname(path)
        dirname = (join(FILE_ROOT, username, dirname))
        filename = os.path.split(path)[-1]

        if not check_path(dirname, username):
            abort(HTTP_FORBIDDEN)

        return dirname, filename

    def _update_user_path(self, username, path):
        """
        Make all needed updates to <userdata> (dict and disk) after a post or a put.
        Return the last modification int timestamp of written file.
        :param username: str
        :param path: str
        :return: int
        """
        filepath = userpath2serverpath(username, path)
        last_server_timestamp = file_timestamp(filepath)
        userdata[username][LAST_SERVER_TIMESTAMP] = last_server_timestamp
        userdata[username]['files'][normpath(path)] = [last_server_timestamp, calculate_file_md5(open(filepath, 'rb'))]
        save_userdata()    
        return last_server_timestamp

    @auth.login_required
    def post(self, path):
        """
        Upload an authenticated user file to the server, given the path relative to the user directory.
        Return the file timestamp of the file created in the server.
        The file must not exist in the server, otherwise only return an http forbidden code.
        :param path: str
        """
        username = auth.username()

        upload_file = request.files['file']
        md5 = request.form['md5']
        dirname, filename = self._get_dirname_filename(path)

        if calculate_file_md5(upload_file) != md5:
            abort(HTTP_CONFLICT)

        if not os.path.exists(dirname):
            os.makedirs(dirname)
        else:
            if os.path.isfile(join(dirname, filename)):
                abort(HTTP_FORBIDDEN)

        filepath = join(dirname, filename)
        upload_file.save(filepath)

        # Update and save <userdata>, and return the last server timestamp.
        last_server_timestamp = self._update_user_path(username, path)

        resp = jsonify({LAST_SERVER_TIMESTAMP: last_server_timestamp})
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
        username = auth.username()
        upload_file = request.files['file']
        md5 = request.form['md5']
        dirname, filename = self._get_dirname_filename(path)

        if calculate_file_md5(upload_file) != md5:
            abort(HTTP_CONFLICT)

        filepath = join(dirname, filename)
        if os.path.isfile(filepath):
            upload_file.save(filepath)
        else:
            abort(HTTP_NOT_FOUND)

        # Update and save <userdata>, and return the last server timestamp.
        last_server_timestamp = self._update_user_path(username, path)

        resp = jsonify({LAST_SERVER_TIMESTAMP: last_server_timestamp})
        resp.status_code = HTTP_CREATED
        return resp


api.add_resource(Files, '{}/files/<path:path>'.format(URL_PREFIX), '{}/files/'.format(URL_PREFIX))
api.add_resource(Actions, '{}/actions/<string:cmd>'.format(URL_PREFIX))
api.add_resource(Users, '{}/users/<string:username>'.format(URL_PREFIX))
api.add_resource(UsersReset, '{}/users/<string:username>/reset'.format(URL_PREFIX))
api.add_resource(UsersFacility, '{}/getusers/<string:username>'.format(URL_PREFIX))

# Set the flask.ext.mail.Mail instance
mail = configure_email()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', default=False, action='store_true',
                        help='set console verbosity level to DEBUG (4) [default: %(default)s]')
    parser.add_argument('--verbose', default=False, action='store_true',
                        help='set console verbosity level to INFO (3) [default: %(default)s]. \
                        Ignored if --debug option is set.')
    parser.add_argument('-v', '--verbosity', const=1, default=1, type=int, choices=range(5), nargs='?',
                        help='set console verbosity: 0=CRITICAL, 1=ERROR, 2=WARN, 3=INFO, 4=DEBUG. \
                        [default: %(default)s]. Ignored if --verbose or --debug option is set.')
    parser.add_argument('-H', '--host', default='0.0.0.0',
                        help='set host address to run the server. [default: %(default)s].')
    args = parser.parse_args()

    if args.debug:
        # If set to True, win against verbosity and verbose parameter
        console_handler.setLevel(logging.DEBUG)
    elif args.verbose:
        # If set to True, win against verbosity parameter
        console_handler.setLevel(logging.INFO)
    else:
        levels = [logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
        console_handler.setLevel(levels[args.verbosity])

    logger.debug('File logging level: {}'.format(file_handler.level))

    if not os.path.exists(EMAIL_SETTINGS_FILEPATH):
        # ConfigParser.ConfigParser.read doesn't tell anything if the email configuration file is not found.
        raise ServerConfigurationError('Email configuration file "{}" not found!'.format(EMAIL_SETTINGS_FILEPATH))

    userdata.update(load_userdata())
    init_root_structure()
    app.run(host=args.host, debug=args.debug)

if __name__ == '__main__':
    main()
