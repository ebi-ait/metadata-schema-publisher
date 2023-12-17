import os
from unittest import TestCase
import pytest
from assertpy import assert_that

from file_util import load_json
from metadata_schema import MetadataSchema, get_version, MetadataSchemaError, get_relative_url


@pytest.fixture
def schema_base_url():
    return 'https://schema.morphic.bio/'


@pytest.fixture
def version_map(test_dir):
    return load_json(f'{test_dir}/files/morphic/versions.json')


@pytest.fixture
def test_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def study_schema_json(test_dir):
    return load_json(f'{test_dir}/files/morphic/study.json')


def test_json_schema__returns_dict_with_schema_urls_in_id_and_refs__when_version_from_path_is_found(
        test_dir, study_schema_json, version_map, schema_base_url
):
    # given
    schema_path = 'type/project/study'

    # when
    schema = MetadataSchema(study_schema_json, schema_path)

    # then
    expected = load_json(f'{test_dir}/files/morphic/study-schema.json')
    actual = schema.get_json_schema(version_map, schema_base_url)
    assert_that(actual).contains('$id')
    assert_that(actual).is_equal_to(expected, include='$id')
    assert_that(actual).is_equal_to(expected)


@pytest.fixture
def schema_json():
    return {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "allOf": [
            {
                "type": "object",
                "$ref": "system/document.json",
                "$comment": "This loads the system needed properties outside the 'content' field. For implementation "
                            "outside of MorPhiC, please ensure the system properties satisfy your implementation. "
                            "These properties are not meant for the user to see.",
                "properties": {
                    "accessions": {
                        "description": "An International Nucleotide Sequence Database Collaboration (INSDC) or "
                                       "BioSamples (BSD) sample accession.",
                        "title": "Sample accession"
                    }
                }
            }
        ]
    }


@pytest.fixture
def expected_updated_schema():
    return {
        "$schema": "https://json-schema.org/draft/2019-09/schema",
        "allOf": [
            {
                "type": "object",
                "$ref": "https://schema.morphic.bio/system/0.0.1/document",
                "$comment": "This loads the system needed properties outside the 'content' field. For implementation "
                            "outside of MorPhiC, please ensure the system properties satisfy your implementation. "
                            "These properties are not meant for the user to see.",
                "properties": {
                    "accessions": {
                        "description": "An International Nucleotide Sequence Database Collaboration (INSDC) or "
                                       "BioSamples (BSD) sample accession.",
                        "title": "Sample accession"
                    }
                }
            }
        ]
    }


def test_update_refs_urls__returns_json_with_updated_refs__when_all_ref_versions_found(
        test_dir, schema_base_url, version_map, schema_json, expected_updated_schema
):
    # given
    schema_path = 'type/project/study'

    # when
    schema = MetadataSchema(schema_json, schema_path).update_refs_urls(version_map, schema_base_url)

    # then
    assert_that(schema).is_equal_to(expected_updated_schema)
