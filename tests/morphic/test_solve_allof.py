import json
import os
from unittest.mock import MagicMock
from assertpy import assert_that
import pytest

from file_util import load_json
from handler import solve_allof


@pytest.fixture
def test_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def document_schema(test_dir):
    return load_json(f'{test_dir}/files/morphic/solve_allof/document.json')


@pytest.fixture
def study_schema_allof(test_dir):
    return load_json(f'{test_dir}/files/morphic/solve_allof/study_with_allof.json')

@pytest.fixture
def study_schema_solved_allof(test_dir):
    return load_json(f'{test_dir}/files/morphic/solve_allof/study_with_solved_allof.json')


@pytest.fixture
def path_processing():
    return 'json_schema/type/project/study.json'


@pytest.fixture
def repo():
    # Mock the repo object
    return MagicMock()


@pytest.fixture
def branch_name():
    # Mock the branch_name
    return "main"


@pytest.fixture
def base_server_path():
    # Mock the base_server_path
    return "json_schema"


def test_solve_allof_resolves_ref(repo, path_processing, branch_name, base_server_path, study_schema_allof,
                                  document_schema, study_schema_solved_allof):
    # Mock the repo.get_contents method to return system_schema
    repo.get_contents.return_value.decoded_content.decode.return_value = json.dumps(document_schema)

    # Call the solve_allof method
    result_schema = solve_allof(repo, path_processing, branch_name, base_server_path, study_schema_allof)

    # Assert the result
    expected_result = study_schema_solved_allof
    assert_that(result_schema).is_equal_to(expected_result)