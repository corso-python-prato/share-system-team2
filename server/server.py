# !/usr/bin/env python
#-*- coding: utf-8 -*-
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

URL_PREFIX = '/API/V1'
# Users login data are stored in a json file in the server
USERDATA_FILENAME = 'userdata.json'


app = Flask(__name__)
api = Api(app)
auth = HTTPBasicAuth()


def _read_file(filename):
    """
    This function reads and returns the content of the file.
    """
    with open(filename, "rb") as f:
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
        with open(USERDATA_FILENAME, 'rb') as fp:
            data = json.load(fp, 'utf-8')
            print('{:,} users loaded'.format(len(data)))
    except IOError:
        print('No users loaded.')
    return data

def save_userdata(data):
    with open(USERDATA_FILENAME, 'wb') as fp:
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

@app.route("{}/signup".format(URL_PREFIX), methods=['POST'])
def create_user():
    """
    Handle the creation of a new user.
    """
    # Example of creation using requests:
    # requests.post('http://127.0.0.1:5000/API/V1/signup', data={'username': 'Pippo', 'password': 'ciao'})
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
    else:
        response = 'Error: username or password is missing', HTTP_BAD_REQUEST
    print(response)
    return response

class Files(Resource):
    @auth.login_required
    def get(self, path):
        print request.authorization
        dirname = os.path.join("upload",os.path.dirname(path))
        real_dirname = os.path.realpath(dirname)
        real_root = os.path.realpath('upload/')

        if real_root not in real_dirname:
            abort(HTTP_FORBIDDEN)
        if not os.path.exists(dirname):
            abort(HTTP_NOT_FOUND)
        s_filename = secure_filename(os.path.split(path)[-1])

        try:
            response = make_response(_read_file(os.path.join("upload",path)))
        except IOError:
            response = 'File not found', HTTP_NOT_FOUND
        else:
            response.headers["Content-Disposition"] = "attachment; filename=%s" % s_filename
        return response

    @auth.login_required
    def post(self, path):
        upload_file = request.files["file"]
        dirname = os.path.dirname(path)
        dirname = "upload/" + dirname
        real_dirname = os.path.realpath(dirname)
        real_root = os.path.realpath('upload/')

        if real_root not in real_dirname:
            abort(HTTP_FORBIDDEN)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        filename = os.path.split(path)[-1]   
        upload_file.save(os.path.join(dirname, filename))
        return "", HTTP_CREATED


api.add_resource(Files, "{}/files/<path:path>".format(URL_PREFIX))

if __name__ == "__main__":
    userdata = load_userdata()
    app.run(host="0.0.0.0", debug=True)