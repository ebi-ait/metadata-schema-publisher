import base64
import collections.abc
import json
import os
from functools import cache
import time
from json import JSONDecodeError

import boto3
import jwt
import requests
from github import Github, GithubException

from metadata_schema import MetadataSchema, get_relative_url, MetadataSchemaError

BRANCH_CONFIG = {
    'develop': 'DEV_BUCKET',
    'integration': 'INTEGRATION_BUCKET',
    'staging': 'STAGING_BUCKET',
    'main': 'PROD_BUCKET'
}

INGEST_API = {
    'develop': 'DEV_INGEST_API',
    'integration': 'INTEGRATION_INGEST_API',
    'staging': 'STAGING_INGEST_API',
    'main': 'MAIN_INGEST_API'
}

SCHEMA_URL = {
    'main': 'MAIN_SCHEMA_URL',
    'develop': 'DEV_SCHEMA_URL',
    'integration': 'INTEGRATION_SCHEMA_URL',
    'staging': 'STAGING_SCHEMA_URL'
}

PROJECT_IDENTIFIER = os.getenv('PROJECT_IDENTIFIER_CONFIG')
BRANCH_REFS = os.getenv('BRANCH_REFS_CONFIG', '').split(',')

UNVERSIONED_FILES = os.getenv('UNVERSIONED_FILES_CONFIG', '').split(',')

DEFAULT_JWT_AUDIENCE = os.getenv('DEFAULT_JWT_AUDIENCE_CONFIG')

JWT_AUDIENCE_TARGET_BRANCH = os.getenv('JWT_AUDIENCE_TARGET_BRANCH_CONFIG')


def get_service_jwt(service_credentials, audience):
    iat = time.time()
    exp = iat + 3600
    payload = {'iss': service_credentials["client_email"],
               'sub': service_credentials["client_email"],
               'aud': audience,
               'iat': iat,
               'exp': exp,
               'scope': ["openid", "email", "offline_access"]
               }
    additional_headers = {'kid': service_credentials["private_key_id"]}
    signed_jwt = jwt.encode(payload, service_credentials["private_key"], headers=additional_headers,
                            algorithm='RS256').decode()
    return signed_jwt


def notify_ingest(branch_name, service_account):
    if is_notify_actions_enabled():
        if is_dry_run():
            print('DRY RUN: notify ingest ' + branch_name)
        else:
            ingest_base_url = INGEST_API.get(branch_name)
            schema_update_url = f'{ingest_base_url}/schemas/update'

            audience = DEFAULT_JWT_AUDIENCE
            if branch_name == JWT_AUDIENCE_TARGET_BRANCH:
                audience = "https://data.humancellatlas.org/"

            if service_account:
                token = get_service_jwt(service_account, audience)
                headers = {'Authorization': f'Bearer {token}'}
            else:
                headers = {}
            r = requests.post(schema_update_url, headers=headers)
            r.raise_for_status()
        print(f'[{PROJECT_IDENTIFIER}] Notified Ingest for branch {branch_name} '
              f'- Schema Update URL: {schema_update_url}')


def get_access_token(secrets):
    access_token = secrets.get('GITHUB_ACCESS_TOKEN')
    if not access_token:
        raise Exception('A GitHub access token is required to communicate with GitHub API')
    return access_token


def get_service_account(secrets):
    if 'GCP_SERVICE_ACCOUNT' in secrets:
        service_account = secrets.get('GCP_SERVICE_ACCOUNT')
        if not service_account:
            raise Exception('A GCP service account is required to communicate with Ingest API')
        return json.loads(service_account)
    else:
        return {}


def on_github_push(event, context):
    message = _process_event(event)
    ref = message["ref"]
    secret_name = os.environ['SECRET_NAME']
    secrets = json.loads(get_secret(secret_name))
    access_token = get_access_token(secrets)
    service_account = get_service_account(secrets)

    print(f'Executing for Project: {PROJECT_IDENTIFIER}')
    if ref in BRANCH_REFS:
        print(f'Processing branch: {ref}')
        repo_name = message["repository"]["full_name"]
        repo = Github(access_token).get_repo(repo_name)
        branch = repo.get_branch(ref)
        pusher = message["pusher"]["name"]
        notification_message = "Commit to " + ref + " detected on " + repo_name + " branch " + branch.name + " by " + \
                               pusher
        print(notification_message)
        _send_notification(notification_message, context)
        server_path = 'json_schema'
        versions_file = repo.get_contents(server_path + "/versions.json", branch.name)
        version_numbers_str = base64.b64decode(versions_file.content).decode("utf-8")
        version_map = json.loads(version_numbers_str)

        result, errors = _process_directory(repo, branch.name, server_path, server_path, version_map, context)
        result_str = "\n".join(result)
        result_message = ""

        if len(result) == 0:
            result_message = result_message + f"No schema changes published. Error count {len(errors)}"
        else:
            result_message = result_message + f"New schema changes published:\n{result_str}\nError count {len(errors)}"
            time.sleep(5)
            notify_ingest(branch.name, service_account)

        print(result_message)
        _send_notification(result_message, context)

    else:
        result = []
        errors = []

    response = {
        "statusCode": 200,
        "body": json.dumps({
            "created": result,
            "errors": errors
        })
    }
    if is_dry_run():
        print("DRY RUN:" + json.dumps(response))
    return response


@cache
def is_dry_run():
    return os.getenv('METADATA_SCHEMA_PUBLISHER_DRY_RUN', 'False').lower() in ('y', 'yes', 't', 'true', 'on', '1')


def is_notify_actions_enabled():
    return os.getenv('NOTIFY_ACTIONS', 'true').lower() in ('y', 'yes', 't', 'true', 'on', '1')


def is_solve_allof_enabled():
    return os.getenv('SOLVE_ALLOF', 'false').lower() in ('y', 'yes', 't', 'true', 'on', '1')


def _process_event(event):
    message = json.loads(event["body"])
    return message


def _process_directory(repo, branch_name, base_server_path, server_path, version_map, context):
    print(f'[{PROJECT_IDENTIFIER}] Processing {server_path} in {branch_name} branch of {repo.name}')
    created_list = []
    error_list = []
    contents = repo.get_dir_contents(server_path, branch_name)
    for content in contents:
        if content.type == 'dir':
            results, errors = _process_directory(repo, branch_name, base_server_path, content.path, version_map,
                                                 context)
            created_list.extend(results)
            error_list.extend(errors)
        else:
            try:
                path = content.path
                file_root, file_extension = os.path.splitext(path)
                if path.endswith('versions.json') or path.endswith('.md'):
                    print("- skipping: " + path)
                else:
                    print("- processing: " + path)
                    file_content = repo.get_contents(path, branch_name)
                    data = base64.b64decode(file_content.content)
                    json_data = json.loads(data.decode('utf8'))

                    if is_solve_allof_enabled():
                        json_data = solve_allof(repo, path, branch_name, base_server_path, json_data)

                    relative_path = path.replace(base_server_path + "/", "")
                    relative_path = relative_path.replace(".json", "")
                    key = None

                    if relative_path in UNVERSIONED_FILES:
                        key = relative_path
                    else:
                        schema_base_url = resolve_schema_base_url(branch_name)
                        metadata_schema = MetadataSchema(json_data, relative_path)
                        json_data = metadata_schema.get_json_schema(version_map, schema_base_url)
                        key = get_relative_url(relative_path, version_map)

                    if key is None:
                        print("- could not find key for: " + path)
                    else:
                        created = _upload(key, branch_name, json_data, context)
                        if created:
                            created_list.append(key)

            except(GithubException, IOError, JSONDecodeError, MetadataSchemaError) as e:
                error_list.append({'path': 'content.path', 'error': str(e)})
                print(f'Error processing {content.path} in branch {branch_name}: {e}')
    return created_list, error_list


def update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def solve_allof(repo, path_processing, branch_name, base_server_path, schema):
    if 'allOf' in schema:
        print(f"[{PROJECT_IDENTIFIER}] - Solving 'allOf' property in {path_processing} for branch {branch_name}")
        allOf = schema['allOf']
        for subschema in allOf:
            if "$ref" not in subschema:
                continue
            try:
                path = f"{base_server_path}/system/document.json"
                file_content = repo.get_contents(path, branch_name)
                system = json.loads(file_content.decoded_content.decode('utf-8'))
                subschema = update(subschema, system)
            except Exception as e:
                print(f"Error resolving '$ref' in {path_processing} for branch {branch_name}: {e}")

        schema['allOf'][0] = subschema
        # Delete redundant info
        if subschema:
            del subschema['$ref']
            del subschema['$schema']
    return schema


def resolve_schema_base_url(branch_name):
    schema_base_url = os.getenv('METADATA_SCHEMA_PUBLISHER_SCHEMA_BASE_URL')
    if not schema_base_url:
        schema_base_url_var = SCHEMA_URL.get(branch_name)
        schema_base_url = os.environ.get(schema_base_url_var)
    if schema_base_url[-1] != '/':
        schema_base_url = schema_base_url + '/'
    return schema_base_url


def _upload(key, branch_name, file_data, context):
    if is_dry_run():
        output_dir = 'dryrun'
        output_path = output_dir + '/' + key
        pos = output_path.rfind('/')
        os.makedirs(output_path[0:pos], exist_ok=True)
        with open(output_path, 'w') as outfile:
            json.dump(file_data, outfile, indent=2)
        print("Output: " + output_path)
        return True
    else:
        bucket_env_var = BRANCH_CONFIG.get(branch_name)

        bucket = os.environ[bucket_env_var]

        s3 = boto3.client('s3')

        if (not _key_exists(s3, bucket, key)) or (key in UNVERSIONED_FILES):
            try:
                s3.put_object(Bucket=bucket,
                              Key=key,
                              Body=json.dumps(file_data, indent=2),
                              ContentType='application/json',
                              CacheControl="no-cache")
                return True
            except Exception as e:
                error_message = 'Error uploading ' + key
                print(error_message, e)
                _send_notification(error_message, context)
        else:
            return False


def _key_exists(s3, bucket, key):
    response = s3.list_objects_v2(
        Bucket=bucket,
        Prefix=key,
    )
    for obj in response.get('Contents', []):
        if obj['Key'] == key:
            return obj['Size']


def _send_notification(message, context):
    if is_notify_actions_enabled():
        if is_dry_run():
            print("DRY RUN:" + message)
        else:
            topic_name = os.environ['TOPIC_NAME']
            account_id = context.invoked_function_arn.split(":")[4]
            if account_id != "Fake":
                print("Sending notification to " + topic_name)
                topic_arn = "arn:aws:sns:" + os.environ['AWS_REGION'] + ":" + account_id + ":" + topic_name
                sns = boto3.client(service_name="sns")
                sns.publish(
                    TopicArn=topic_arn,
                    Message=message
                )
            else:
                print("Skipping notification: " + message)
    else:
        print(f'Notifications are disabled - Message: {message}')


def sns_to_slack(event, context):
    print(event)
    sns = event['Records'][0]['Sns']
    message = sns['Message']

    secret_name = os.environ['SECRET_NAME']
    secret = get_secret(secret_name)
    secrets = json.loads(secret)

    webhook_url = secrets.get('SLACK_URL')

    if not webhook_url:
        raise Exception('Could not find the slack webhook url!')

    payload = {
        'text': message
    }
    r = requests.post(webhook_url, json=payload)
    return r.status_code


def get_secret(secret_name, region_name=None):
    if not region_name:
        region_name = os.environ['AWS_PROVIDER_REGION']

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    get_secret_value_response = client.get_secret_value(
        SecretId=secret_name
    )

    # Decrypts secret using the associated KMS CMK.
    # Depending on whether the secret is a string or binary, one of these fields will be populated.
    if 'SecretString' in get_secret_value_response:
        return get_secret_value_response['SecretString']
    else:
        return base64.b64decode(get_secret_value_response['SecretBinary'])
