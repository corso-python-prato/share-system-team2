import unittest
import server
import io
import os

class TestRequests(unittest.TestCase):
    def setUp(self):
        self.app = server.app.test_client()

    def test_files_get_with_auth(self):
        test = self.app.get("/API/V1/files/file1.txt")
        self.assertTrue("200" in str(test))

    def test_files_get_without_auth(self):
        test = self.app.get("/API/V1/files/file1.txt")
        self.assertTrue("200" in str(test))

    def test_files_get_with_not_existing_file(self):
        test = self.app.get("/API/V1/files/file1.cat")
        self.assertTrue("500" in str(test))

    def test_files_post_with_auth(self):
        test = self.app.post("/API/V1/files/test/myfile.dat", data=dict(
            file=(io.BytesIO(b"this is a test"), "test.pdf"),), follow_redirects=True)
        self.assertTrue("201" in str(test))
        self.assertTrue(os.path.isfile("upload/test/myfile.dat"))

    def test_files_post_with_not_allowed_path(self):
        test = self.app.post("/API/V1/files/../../../test/myfile2.dat", data=dict(
            file=(io.BytesIO(b"this is a test"), "test.pdf"),), follow_redirects=True)
        self.assertTrue("403" in str(test))
        self.assertFalse(os.path.isfile("upload/../../../test.myfile2.dat"))


if __name__ == "__main__":
    unittest.main()