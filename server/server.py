#!/usr/bin/env python
#-*- coding: utf-8 -*-
from flask import Flask, make_response, request
from flask.ext.httpauth import HTTPBasicAuth
import os


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


FILENAME = "myfile.dat"


def file_content(filename): 		#This function returns the content of the file that is being download
	with open(filename, "rb") as f:
		content = f.read()
	return content

@app.route("/download")				# This function downloads an existing file on server which is "myfile.dat"
def download():
	response = make_response(file_content(FILENAME))
	response.headers["Content-Disposition"] = "attachment; filename=%s" % FILENAME
	return response

@app.route("/upload", methods = ["POST"])
def upload():
	upload_file = request.files['file']	
	upload_file.save(os.path.join("upload", upload_file.filename))
	return "201"
	
if __name__ == "__main__":
	app.run(debug=True)
