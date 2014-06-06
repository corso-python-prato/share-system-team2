# !/usr/bin/env python
#-*- coding: utf-8 -*-
import os
from flask import Flask, make_response, request, abort
from flask.ext.httpauth import HTTPBasicAuth
from werkzeug import secure_filename

URL_PREFIX = '/API/V1'

user_login_info = {
    "luca": "luca",
    "iacopo": "iacopo"
}

app = Flask(__name__)
auth = HTTPBasicAuth()


@auth.get_password
def get_pw(username):
    return user_login_info.get(username)


@app.route(URL_PREFIX)
def hello():
    return "Hello. This resource is available without authentication."


@app.route("{}/test".format(URL_PREFIX))
@auth.login_required
def index():
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
    app.run(debug=True)
