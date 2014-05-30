#!/usr/bin/env python
#-*- coding: utf-8 -*-

from flask import Flask, make_response, request
import os

FILENAME = "myfile.dat"
app = Flask(__name__)

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

