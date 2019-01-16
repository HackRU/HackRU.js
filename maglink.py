from pymongo import MongoClient
import random
import datetime
import string
from datetime import datetime, timedelta

import use_sparkpost
import config
from schemas import *

def forgotUser(event, magiclinks, tests):
    user = tests.find_one({"email":event['email']})
    if user:
        magiclink = 'forgot-' +  ''.join([random.choice(string.ascii_letters + string.digits) for n in range(32)])
        obj_to_insert = {}
        obj_to_insert['email'] = event['email']
        obj_to_insert['link'] = magiclink
        obj_to_insert['forgot'] = True
        obj_to_insert[ "valid_until"] = (datetime.now() + timedelta(hours=3)).isoformat()
        magiclinks.insert_one(obj_to_insert)
        link_base = event.get('link_base', 'https://hackru.org/magic/{}')
        rv = use_sparkpost.send_email(event['email'], link_base.format(magiclink),True, None)
        if rv['statusCode'] != 200:
            return rv
        return config.add_cors_headers({"statusCode":200,"body":"Forgot password link has been emailed to you"})
    else:
        return config.add_cors_headers({"statusCode":400,"body":"Invalid email: please create an account."})

def directorLink(magiclinks, numLinks, event, user):
    links_list = []
    permissions = []
    for i in event['permissions']:
            permissions.append(i)
    for j in range(min(numLinks, len(event['emailsTo']))):
        magiclink = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(32)])
        obj_to_insert = {}
        obj_to_insert['permissions'] = permissions
        obj_to_insert['email'] = event['emailsTo'][j]
        obj_to_insert['forgot'] = False
        obj_to_insert['link'] = magiclink
        obj_to_insert["valid_until"] = (datetime.now() + timedelta(hours=3)).isoformat()
        magiclinks.insert_one(obj_to_insert)
        sent = use_sparkpost.send_email(obj_to_insert['email'],magiclink,False, user)['body']
        links_list.append((magiclink, sent))
    return links_list

@ensure_schema({
    "type": "object",
    "properties": {
        "email": {"type": "email"},
        "token": {"type": "string"},
        "permissions": {"type": "array"},
        "emailsTo": {"type": "array"},
        "numLinks": {"type": "integer"}
    },
    "required": ["email", "token", "permissions", "emailsTo", "numLinks"]
})
@ensure_logged_in_user()
@ensure_role([['director']])
def do_director_link(event, magiclinks, user):
    numLinks = event.get('numLinks', 1)
    links_list = directorLink(magiclinks, numLinks, event, user)
    return config.add_cors_headers({"statusCode":200,"body":links_list})

@ensure_schema({
    "type": "object",
    "properties": {
        "email": {"type": "email"},
    },
    "required": ["email"]
})
def genMagicLink(event, context):
    """
       The event object expects and email and  checks if it is a valid request to generate the magic link
    """
    client = MongoClient(config.DB_URI)
    db = client[config.DB_NAME]
    db.authenticate(config.DB_USER,config.DB_PASS)
    tests = db[config.DB_COLLECTIONS['users']]
    magiclinks = db[config.DB_COLLECTIONS['magic links']]


    if 'forgot' in event:
        return forgotUser(event, magiclinks, tests)
    return do_director_link(event, magiclinks)
