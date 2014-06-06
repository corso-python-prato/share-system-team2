# !/usr/bin/env python
#-*- coding: utf-8 -*-
import os
import json

from flask import Flask, make_response, request, abort
from flask.ext.httpauth import HTTPBasicAuth
from werkzeug import secure_filename
from passlib.hash import sha256_crypt


URL_PREFIX = '/API/V1'

# Users login data are stored in a json file in the server
USERDATA_FILENAME = 'userdata.json'

app = Flask(__name__)
auth = HTTPBasicAuth()


def load_userdata():
    data = {}
    try:
        with open(USERDATA_FILENAME, 'rb') as fp:
            data = json.load(fp, 'utf-8')
            print('{:,} users loaded'.format(len(data)))
    except IOError:
        print('No users loaded.')
    return data


def save_userdata(user_login_info):
    with open(USERDATA_FILENAME, 'wb') as fp:
        json.dump(user_login_info, fp, 'utf-8')
    print('Saved {:,} users'.format(len(user_login_info)))


def encrypt_password(password):
    """
    Return the password encrypted as a string.
    :rtype : str
    """
    return sha256_crypt.encrypt(password)

#
# @auth.get_password
# def get_pw(username):
#     return user_login_info.get(username)


@auth.verify_password
def verify_password(username, password):
    """
    We redefine this function to check password with the encrypted one.
    """
    if not username:
        # Warning/info?
        return False
    stored_pw = user_login_info.get(username)
    if stored_pw:
        res = sha256_crypt.verify(password, stored_pw)
    else:
        print('User "{}" does not exist!'.format(username))
        res = False
    return res


@app.route(URL_PREFIX)
def hello():
    return "Hello. This resource is available without authentication."


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
        if username in user_login_info:
            # user already exists!
            response = 'Error: username already exists!', 403
        else:
            user_login_info[username] = encrypt_password(password)
            response = 'User "{}" created'.format(username), 201
            save_userdata(user_login_info)
    else:
        response = 'Error: username or password is missing', 400
    print(response)
    return response


@app.route("{}/test".format(URL_PREFIX))
@auth.login_required
def index():
    print('Authenticated resource')
    return "ROUTE TEST - Logged as: %s!" % auth.username()


def file_content(filename):
    """
    This function returns the content of the file that is being download
    """
    with open(filename, "rb") as f:
        content = f.read()
    return content

@app.route("/files/<filename>")     
def download(filename):
    """
    This function downloads <filename> from  server directory 'upload'
    """
    s_filename = secure_filename(filename)
    response = make_response(file_content(os.path.join("upload", s_filename)))
    response.headers["Content-Disposition"] = "attachment; filename=%s" % s_filename
    return response

@app.route("/files/<path:varargs>", methods = ["POST"])
def upload(varargs):
    """
        This function uploads a file to the server in the 'upload' folder
    """
    upload_file = request.files["file"]
    path = []
        
    dirname = os.path.dirname(varargs)
    dirname = "upload/" + dirname
    real_dirname = os.path.realpath(dirname)
    real_root = os.path.realpath('upload/')

    if real_root not in real_dirname:
        abort(403)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    filename = os.path.split(varargs)[-1]   
    upload_file.save(os.path.join(dirname, filename))
    return "", 201

if __name__ == "__main__":
    user_login_info = load_userdata()
    app.run(debug=True)
