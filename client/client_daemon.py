#!/usr/bin/env python
#-*- coding: utf-8 -*-


import select
import socket
import struct
import json


COMMANDS = {
    # 'cmd': api.<cmd>   --> ex. 'downloadFile': api.download_file
}


def dispatcher(data):
    """It dispatch cmd and args to the api manager object"""

    cmd = data.keys()[0]  # it will be always one key
    args = data[cmd]  # it will be a dict specifying the args

    COMMANDS[cmd](args)  # fix-it: use try...except to manage exception


def serve_forever():
    # fix-it: import info from config file
    host = 'localhost'
    port = 50001
    backlog = 5
    int_size = struct.calcsize('!i')

    deamon_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    deamon_server.bind((host, port))
    deamon_server.listen(backlog)
    r_list = [deamon_server]

    running = 1
    while running:
        r_ready, w_ready, e_ready = select.select(r_list, [], [])

        for s in r_ready:

            if s == deamon_server:
                # handle the server socket
                client, address = deamon_server.accept()
                r_list.append(client)
            else:
                # handle all other sockets
                lenght = s.recv(int_size)
                if lenght:
                    lenght = int(struct.unpack('!i', lenght)[0])
                    data = s.recv(lenght)
                    data = json.loads(data)
                    dispatcher(data)
                else:
                    s.close()
                    r_list.remove(s)
    deamon_server.close()


if __name__ == "__main__":
    serve_forever()

