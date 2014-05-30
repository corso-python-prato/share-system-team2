#!/usr/bin/env python
#-*- coding: utf-8 -*-

from flask import Flask, make_response, request
from werkzeug import secure_filename
import os

app = Flask(__name__)

def file_content(filename): 
	"""
		This function returns the content of the file that is being download
	"""		
	with open(filename, "rb") as f:
		content = f.read()
	return content

@app.route("/download/<filename>")				
def download(filename):
	"""
		This function downloads <filename> from  server directory 'upload'  
	"""
	s_filename = secure_filename(filename)
	response = make_response(file_content(os.path.join("upload", s_filename)))
	response.headers["Content-Disposition"] = "attachment; filename=%s" % s_filename
	return response

@app.route("/upload", methods = ["POST"])
def upload():
	"""
		This function uploads a file to the server in the 'upload' folder
	"""
	upload_file = request.files["file"]	
	filename = secure_filename(upload_file.filename)
	upload_file.save(os.path.join("upload", filename))
	return "", 201

if __name__ == "__main__":
	app.run(debug=True)

