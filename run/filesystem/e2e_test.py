# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This sample creates a secure two-service application running on Cloud Run.
# This test builds and deploys the two secure services
# to test that they interact properly together.

import datetime
import os
import subprocess
from urllib import request
import uuid

import pytest

# Unique suffix to create distinct service names
SUFFIX = uuid.uuid4().hex[:10]
PROJECT = os.environ['GOOGLE_CLOUD_PROJECT']


@pytest.fixture
def deployed_service():
    # Deploy image to Cloud Run
    service_name = f'filesystem-{SUFFIX}'
    connector = os.environ['CONNECTOR']
    ip_address = os.environ['IP_ADDRESS']

    subprocess.run(
        [
            'gcloud',
            'alpha',
            'run',
            'deploy',
            service_name,
            '--source',
            '.',
            '--project',
            PROJECT,
            '--region=us-central1',
            '--no-allow-unauthenticated',
            f'--vpc-connector={connector}',
            '--execution-environment=gen2',
            f'--update-env-vars=IP_ADDRESS={ip_address},FILE_SHARE_NAME=vol1'
        ],
        check=True,
    )

    yield service_name

    subprocess.run(
        [
            'gcloud',
            'run',
            'services',
            'delete',
            service_name,
            '--region=us-central1',
            '--quiet',
            '--project',
            PROJECT,
        ],
        check=True,
    )


@pytest.fixture
def service_url_auth_token(deployed_service):
    # Get Cloud Run service URL and auth token
    service_url = (
        subprocess.run(
            [
                'gcloud',
                'run',
                'services',
                'describe',
                deployed_service,
                '--region=us-central1',
                '--format=value(status.url)',
                '--project',
                PROJECT,
            ],
            stdout=subprocess.PIPE,
            check=True,
        )
        .stdout.strip()
        .decode()
    )
    auth_token = (
        subprocess.run(
            ['gcloud', 'auth', 'print-identity-token'],
            stdout=subprocess.PIPE,
            check=True,
        )
        .stdout.strip()
        .decode()
    )

    yield service_url, auth_token

    # no deletion needed


def test_end_to_end(service_url_auth_token):
    service_url, auth_token = service_url_auth_token
    # Non mnt directory
    req = request.Request(
        service_url, headers={'Authorization': f'Bearer {auth_token}'}
    )
    response = request.urlopen(req)
    assert response.status == 200

    # Mnt directory
    mnt_url = f'{service_url}/mnt/nfs/filestore'
    req = request.Request(
        mnt_url, headers={'Authorization': f'Bearer {auth_token}'}
    )
    response = request.urlopen(req)
    assert response.status == 200

    date = datetime.datetime.utcnow()
    body = response.read()
    weekday = date.strftime('%a')
    month = date.strftime('%b')
    day = date.strftime('%d')
    assert f'{weekday}-{month}-{day}' in body.decode()  # Date
    hour = date.strftime('%H')
    minute = date.strftime('%M')
    assert f'{hour}:{minute}' in body.decode()  # Time
