import pytest
from restapi import app


@pytest.mark.parametrize(
    "query_string, expected_response",
    [
        # Happy path tests
        (
            {"key": "value"},
            "1+0654918011102+http://www.besmart-home.com/fwUpgrade/PR06549/0654918011102.bin",
        ),
        (
            {"version": "latest"},
            "1+0654918011102+http://www.besmart-home.com/fwUpgrade/PR06549/0654918011102.bin",
        ),
        # Edge cases
        (
            {"empty": ""},
            "1+0654918011102+http://www.besmart-home.com/fwUpgrade/PR06549/0654918011102.bin",
        ),
        (
            {},
            "1+0654918011102+http://www.besmart-home.com/fwUpgrade/PR06549/0654918011102.bin",
        ),
        # Error cases - Assuming function behavior for error handling, adjust as necessary
        # Note: This function does not explicitly handle errors, so error cases are hypothetical
    ],
)
def test_getVersion(query_string, expected_response):
    # Arrange
    app.config["TESTING"] = True
    client = app.test_client()

    # Act
    response = client.get("/fwUpgrade/PR06549/version.txt", query_string=query_string)

    # Assert
    assert response.data.decode() == expected_response
    assert response.status_code == 200
