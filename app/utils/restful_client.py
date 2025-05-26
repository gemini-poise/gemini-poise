import requests


class RestfulClient:
    def __init__(self, base_url, headers=None):
        self.base_url = base_url
        self.headers = headers if headers is not None else {}

    def _request(
        self, method, path, params=None, data=None, json_data=None, headers=None
    ):
        url = f"{self.base_url}/{path.lstrip('/')}"

        _headers = self.headers.copy()
        if headers:
            _headers.update(headers)

        try:
            response = requests.request(
                method, url, params=params, data=data, json=json_data, headers=_headers
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as http_err:
            print(
                f"HTTP error occurred: {http_err} - Response: {http_err.response.text}"
            )
            raise
        except requests.exceptions.ConnectionError as conn_err:
            print(f"Connection error occurred: {conn_err}")
            raise
        except requests.exceptions.Timeout as timeout_err:
            print(f"Timeout error occurred: {timeout_err}")
            raise
        except requests.exceptions.RequestException as req_err:
            print(f"An unexpected error occurred: {req_err}")
            raise

    def get(self, path, params=None, headers=None):
        return self._request("GET", path, params=params, headers=headers)

    def post(self, path, data=None, json_data=None, headers=None):
        return self._request(
            "POST", path, data=data, json_data=json_data, headers=headers
        )

    def put(self, path, data=None, json_data=None, headers=None):
        return self._request(
            "PUT", path, data=data, json_data=json_data, headers=headers
        )

    def delete(self, path, params=None, headers=None):
        return self._request("DELETE", path, params=params, headers=headers)

    def patch(self, path, data=None, json_data=None, headers=None):
        return self._request(
            "PATCH", path, data=data, json_data=json_data, headers=headers
        )

    def head(self, path, params=None, headers=None):
        return self._request("HEAD", path, params=params, headers=headers)

    def options(self, path, params=None, headers=None):
        return self._request("OPTIONS", path, params=params, headers=headers)
