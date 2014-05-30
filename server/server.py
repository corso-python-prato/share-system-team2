#!/usr/bin/env python
#-*- coding: utf-8 -*-

from flask import Flask
from flask.ext.httpauth import HTTPBasicAuth


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
    return "Autenticazione non necessaria"


@app.route("{}/test".format(URL_PREFIX))
@auth.login_required
def index():
    return "ROUTE TEST - Autenticato come utente: %s!" % auth.username()


if __name__ == "__main__":
    app.run()