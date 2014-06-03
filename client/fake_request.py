__author__ = 'milly'

from httmock import all_requests, response, HTTMock
import requests


users = {
    # user: pass
}


def create_fake_raise(code, message):
    """
        Creates a bad response to send to client
    """
    @all_requests
    def response_content(url, request):
            headers = {'content-type': 'application/json',
                       'Set-Cookie': 'foo=bar;'}
            content = {'message': 'API rate limit exceeded'}
            return response(code, content, headers, message, 5, request)

    with HTTMock(response_content):
            r = requests.get('https://api.github.com/users/whatever')

    return r


# class Response(object):
#     """Fake response object"""
#     def __init__(self, code):
#         self.status_code = code
# 
#     def raise_for_status(self):
#         pass


def post(url, data):
    if url != 'NEWUSER':
        response = create_fake_raise(404, 'not found')
        return response

    try:
        new_user = data['user']
        password = data['pass']
    except KeyError:
        response = create_fake_raise(401, 'bad arguments')
        return response

    if new_user in users:
        response = create_fake_raise(500, 'User already created')
        return response
    else:
        users[new_user] = password
        response = create_fake_raise(200, 'Uses added Successfully')

    return response




