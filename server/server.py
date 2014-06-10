# !/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json

from flask import Flask, make_response, request, abort
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
DEFAULT_REGISTERED_USER = 'pybox', 'pw'


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
    # Register a fake user on-the-fly to use it with tests under auth
    default_user, default_user_password = DEFAULT_REGISTERED_USER
    data[default_user] = _encrypt_password(default_user_password)

    try:
        with open(_path(USERDATA_FILENAME), 'rb') as fp:
            data = json.load(fp, 'utf-8')
    except IOError:
        pass
    print 'Registered user(s):', ', '.join(data.keys())
    print('{:,} registered user(s) found'.format(len(data)))
    return data


def save_userdata(data):
    with open(_path(USERDATA_FILENAME), 'wb') as fp:
        json.dump(data, fp, 'utf-8')
    print('Saved {:,} users'.format(len(data)))


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
        print('User "{}" does not exist!'.format(username))
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
    print('Creating user...')
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
    print(response)
    return response


class Actions(Resource):
    @auth.login_required
    def post(self, cmd):
        {
        'delete': self._delete,
        'copy': self._copy,
        'move': self._move
        }.get(cmd)()

    def _delete(self):
        pass
    def _move(self):
        pass
    def _copy(self):
        pass


class Files(Resource):
    @auth.login_required
    def get(self, path):

        username = request.authorization['username']
        dirname = os.path.join(FILE_ROOT, username, os.path.dirname(path))
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
    

api.add_resource(Files, '{}/files/<path:path>'.format(URL_PREFIX))
api.add_resource(Actions, '{}/actions/<cmd>'.format(URL_PREFIX))

if __name__ == '__main__':
    userdata = load_userdata()
    app.run(host='0.0.0.0', debug=True)
