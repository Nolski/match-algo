import json
import requests
import os

from typing import Tuple
from datetime import datetime, timedelta

from requests.auth import HTTPBasicAuth
from mongoengine import connect, DynamicDocument
from mongoengine.errors import NotUniqueError
import sys
sys.path.append("..")

from models import JobOpening, JobSeeker, Firm, Match, User, Cron
from const import connect_db, disconnect_db


COMMCARE_USERNAME = os.environ.get('COMMCARE_USERNAME')
COMMCARE_PASSWORD = os.environ.get('COMMCARE_PASSWORD')
CASES_URL = 'https://www.commcarehq.org/a/billy-excerpt/api/v0.5/case/'
USERS_URL = 'https://www.commcarehq.org/a/billy-excerpt/api/v0.5/user/'
headers = {
    'Authorization': f"ApiKey {COMMCARE_USERNAME}:{COMMCARE_PASSWORD}"
}

def create_cases(next_params: str, n: int, CaseClass: DynamicDocument) -> Tuple:
    print(f"Getting cases from {CASES_URL}{next_params}")
    headers = {'Authorization': f"ApiKey {COMMCARE_USERNAME}:{COMMCARE_PASSWORD}"}
    tries = 0
    try:
        resp = requests.get(
            CASES_URL + next_params,
            headers=headers
        )
    except:
        tries += 1
        if tries >= 3:
            request_url = CASES_URL + next_params
            raise Exception(f"Issue getting url {request_url}")
    cases = json.loads(resp.content)
    for c in cases['objects']:
        params = {
            **c['properties'],
            'case_id': c['case_id'],
            'closed': c['closed']
        }
        if c.get('indices').get('parent'):
            params['parent_case_id'] = c['indices']['parent']['case_id']
        upsert_params = {}
        for k in params:
            upsert_params['set__' + k] = params[k]
        case = CaseClass(**params)
        print(f"Creating case {case.case_id}...")
        try:
            case.save()
        except NotUniqueError as e:
            print('modifying existing case...')
            CaseClass.objects(case_id=c['case_id']).modify(upsert=True, **params)
            print(f"{c['case_id']} already exists, skipping...")
        print("saved")
        n += 1

    return (resp, n)

def import_cases(case_type: str, CaseClass: DynamicDocument) -> None:
    old_date = datetime.now() - timedelta(days=2)
    date_str = old_date.strftime("%Y-%m-%d")
    limit_offset = '?limit=70&offset=0'
    case_type = f"&type={case_type}&format=json&date_modified_start={date_str}"
    n = 0
    resp, n = create_cases(limit_offset + case_type, n, CaseClass)

    next_params = json.loads(resp.content)['meta']['next']

    while next_params is not None:
        resp, n = create_cases(next_params, n, CaseClass)
        next_params = json.loads(resp.content)['meta']['next']

    print(f"{n} records processed.")

def create_users(next_params: str, n: int) -> Tuple:
    resp = requests.get(
        USERS_URL + next_params,
        headers=headers
    )
    users = json.loads(resp.content)

    for user in users['objects']:
        user['user_id'] = user['id']
        user.pop('id', None)
        case = User(**user)
        print(f"Creating case {user['user_id']}...")
        try:
            case.save()
        except NotUniqueError as e:
            print('Modifying existing user...')
            print(f"{user['user_id']} already exists, skipping...")
        print("saved")
        n += 1

    return (resp, n)

def import_users() -> None:
    limit_offset = '?limit=20&offset=0&format=json'
    n = 0
    resp, n = create_users(limit_offset, n)

    next_params = json.loads(resp.content)['meta']['next']

    while next_params is not None:
        resp, n = create_users(next_params, n)
        next_params = json.loads(resp.content)['meta']['next']

    print(f"{n} records processed.")



if __name__ == '__main__':
    cron = Cron(date=datetime.now(), status='processing', cron_type='populate_mongo')
    cron_id = None
    connect_db()
    try:
        cron.save()
        cron_id = cron.id
        print("Creating users...")
        import_users()
        cron = Cron.objects.get(id=cron_id)
        cron.imported_information = 'users'
        cron.save()
        print("Creating job openings...")
        import_cases('job-opening', JobOpening)
        cron = Cron.objects.get(id=cron_id)
        cron.imported_information = 'users+job_openings'
        cron.save()
        print("Creating job seekers...")
        import_cases('job-seeker', JobSeeker)
        cron = Cron.objects.get(id=cron_id)
        cron.imported_information = 'users+job_openings+job_seekers'
        cron.save()
        print("Creating firms")
        import_cases('firm', Firm)
        cron = Cron.objects.get(id=cron_id)
        cron.imported_information = 'users+job_openings+job_seekers+firms'
        cron.save()
        print("Creating matches")
        import_cases('match', Match)
        cron = Cron.objects.get(id=cron_id)
        cron.imported_information = 'users+job_openings+job_seekers+firms+match'
        cron.save()
        cron.status = 'finished'
        cron.save()
    except Exception as e:
        cron = Cron.objects.get(id=cron_id)
        cron.status = 'error'
        cron.error = e.message
        cron.save()
    finally:
        disconnect_db()
