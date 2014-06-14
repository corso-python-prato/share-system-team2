import unittest
import connection_manager

import requests
import httpretty
import json

class TestConnectionManager(unittest.TestCase):
    def setUp(self):
        config = {
             "sharing_path": "./sharing_folder",
             "host": "localhost", 
             "port": 50001, 
             "api_suffix": "/API/V1/",
             "server_address":"http://fake.com",
             "user":"pasquale",
             "pass":"secretpass"
            }
      

        self.cm = connection_manager.ConnectionManager(config)

    @httpretty.activate
    def test_do_upload(self):
        httpretty.register_uri(httpretty.POST, "http://pasquale:secretpass@fake.com/API/V1/files",
                          status=201)
        data = {
            "filepath": "foo.txt"
        }
        
        #response = self.cm.do_upload(data)
        #expect(response.status_code).to.equal(201)
        #expect(response.status_code).to.equal(200)

    @httpretty.activate
    def test_get_server_state(self):
        httpretty.register_uri(httpretty.GET, "http://fake.com/API/V1/files",
                          body='{"files": {}}',
                          status=200)               
        a = self.cm.do_get_server_state()
        self.assertEqual(a, json.loads('{"files": {}}'))


if __name__ == '__main__':
    unittest.main()