"""
Description: Sync viewing history with Trakt.tv and Letterboxd
Author: Joost van Someren

Settings:
./sync-settings.ini

  [Plex]
  user_ids: a comma separated list of user ids, only entries for these users will be synced
    The user id for a user can be found in your url in Tautulli when you click on a user.
  
  [Trakt]:
  Update `client_id` with the `client_id` of your registered application, see here:
    https://trakt.tv/oauth/applications > Choose your application

  To set the access code use `urn:ietf:wg:oauth:2.0:oob` as a redirect URI on your application.
  Then execute the script:
  python ./trakt_letterboxd_sync.py --contentType trakt_authenticate --userId -1
  And follow the instructions shown.

  [Letterboxd]
  Update `api_key` and `api_secret` with your Letterboxd API Key and API Shared Secret respectively.
  Look [here](https://letterboxd.com/api-beta/) as for how to receive these credentials.

  To set the access code execute the script:
  python ./trakt_letterboxd_sync.py --contentType letterboxd_authenticate --userId -1
  And follow the instructions shown.

Adding the script to Tautulli:
Tautulli > Settings > Notification Agents > Add a new notification agent > Script

Configuration:
Tautulli > Settings > Notification Agents > New Script > Configuration:

  Script Folder: /path/to/your/scripts
  Script File: ./trakt_letterboxd_sync.py (Should be selectable in a dropdown list)
  Script Timeout: {timeout}
  Description: Trakt.tv and Letterboxd sync
  Save

Triggers:
Tautulli > Settings > Notification Agents > New Script > Triggers:
  
  Check: Watched
  Save
  
Conditions:
Tautulli > Settings > Notification Agents > New Script > Conditions:
  
  Set Conditions: [{condition} | {operator} | {value} ]
  Save
  
Script Arguments:
Tautulli > Settings > Notification Agents > New Script > Script Arguments:
  
  Select: Watched
  Arguments:  --contentType {media_type}
              <episode>--tvdbId {thetvdb_id} --season {season_num} --episode {episode_num}</episode>

  Save
  Close
"""

import os
import sys
import requests
import json
import argparse
import datetime
import time
import uuid
import hmac
from getpass import getpass
from hashlib import sha256
import binascii

from ConfigParser import ConfigParser, NoOptionError, NoSectionError

TAUTULLI_ENCODING = os.getenv('TAUTULLI_ENCODING', 'UTF-8')

credential_path = os.path.dirname(os.path.realpath(__file__))
credential_file = 'sync_settings.ini'

config = ConfigParser()
try:
  with open('%s/%s' % (credential_path,credential_file)) as f:
    config.readfp(f)
except IOError:
  print('ERROR: %s/%s not found' % (credential_path,credential_file))
  sys.exit(1)

def arg_decoding(arg):
  """Decode args, encode UTF-8"""
  return arg.decode(TAUTULLI_ENCODING).encode('UTF-8')

def write_settings():
  """Write config back to settings file"""
  try:
    with open('%s/%s' % (credential_path,credential_file), 'wb') as f:
      config.write(f)
  except IOError:
    print('ERROR: unable to write to %s/%s' % (credential_path,credential_file))
    sys.exit(1)

def sync_for_user(user_id):
  """Returns wheter or not to sync for the passed user_id"""
  try:
    user_ids = config.get('Plex', 'user_ids')
  except (NoSectionError, NoOptionError):
    print('ERROR: %s not setup - missing user_ids' % credential_file)
    sys.exit(1)

  return str(user_id) in user_ids.split(',')

class Trakt:
  def __init__(self, tvdb_id, season_num, episode_num):
    self.tvdb_id = tvdb_id
    self.season_num = season_num
    self.episode_num = episode_num

    try:
      self.client_id = config.get('Trakt', 'client_id')
    except (NoSectionError, NoOptionError):
      print('ERROR: %s not setup - missing client_id' % credential_file)
      sys.exit(1)

    try:
      self.client_secret = config.get('Trakt', 'client_secret')
    except (NoSectionError, NoOptionError):
      print('ERROR: %s not setup - missing client_secret' % credential_file)
      sys.exit(1)

  def get_access_token(self):
    try:
      return config.get('Trakt', 'access_token')
    except (NoSectionError, NoOptionError):
      print('ERROR: %s not setup - missing access_token' % credential_file)
      sys.exit(1)

  def get_refresh_token(self):
    try:
      return config.get('Trakt', 'refresh_token')
    except (NoSectionError, NoOptionError):
      print('ERROR: %s not setup - missing refresh_token' % credential_file)
      sys.exit(1)

  def authenticate(self):
    headers = {
      'Content-Type': 'application/json'
    }

    device_code = self.generate_device_code(headers)
    self.poll_access_token(headers, device_code)

  def generate_device_code(self, headers):
    payload = {
      'client_id': self.client_id
    }

    r = requests.post('https://api.trakt.tv/oauth/device/code', json=payload, headers=headers)
    response = r.json()
    print('Please go to %s and insert the following code: "%s"' % (response['verification_url'], response['user_code']))

    i = raw_input('I have authorized the application! Press ENTER to continue:')

    return response['device_code']

  def poll_access_token(self, headers, device_code): 
    payload = {
      'code': device_code,
      'client_id': self.client_id,
      'client_secret': self.client_secret
    }

    r = requests.post('https://api.trakt.tv/oauth/device/token', json=payload, headers=headers)
    if r.status_code == 400:
      i = raw_input('The device hasn\'t been authorized yet, please do so. Press ENTER to continue:')
      return self.poll_access_token(self, headers, device_code)
    elif r.status_code != 200:
      print('Something went wrong, please try again.')
      sys.exit(1)

    response = r.json()
    config.set('Trakt', 'access_token', response['access_token'])
    config.set('Trakt', 'refresh_token', response['refresh_token'])
    write_settings()

    print('Succesfully configured your Trakt.tv sync!')

  def refresh_access_token(self):
    headers = {
      'Content-Type': 'application/json'
    }

    payload = {
      'refresh_token': self.get_refresh_token(),
      'client_id': self.client_id,
      'client_secret': self.client_secret,
      'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
      'grant_type': 'refresh_token'
    }

    r = requests.post('https://api.trakt.tv/oauth/token', json=payload, headers=headers)
    response = r.json()
    config.set('Trakt', 'access_token', response['access_token'])
    config.set('Trakt', 'refresh_token', response['refresh_token'])
    write_settings()

    print('Refreshed access token succesfully!')

  def get_show(self):
    headers = {
      'Content-Type': 'application/json',
      'trakt-api-version': '2',
      'trakt-api-key': self.client_id
    }

    r = requests.get('https://api.trakt.tv/search/tvdb/' + str(self.tvdb_id) + '?type=show', headers=headers)

    response = r.json()
    return response[0]['show']

  def get_episode(self, show): 
    headers = {
      'Content-Type': 'application/json',
      'trakt-api-version': '2',
      'trakt-api-key': self.client_id
    }

    r = requests.get('https://api.trakt.tv/shows/' + str(show['ids']['slug']) + '/seasons/' + str(self.season_num) + '/episodes/' + str(self.episode_num), headers=headers)
    response = r.json()
    return response

  def sync_history(self):
    access_token = self.get_access_token()
    watched_at = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
    show = self.get_show()
    episode = self.get_episode(show)

    headers = {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + access_token,
      'trakt-api-version': '2',
      'trakt-api-key': self.client_id
    }

    payload = {
     'episodes': [
      {
        'watched_at': watched_at,
        'ids': {
          'trakt': episode['ids']['trakt'],
          'tvdb': episode['ids']['tvdb'],
          'imdb': episode['ids']['imdb'],
          'tmdb': episode['ids']['tmdb']
        }
      }
     ]
    }

    r = requests.post('https://api.trakt.tv/sync/history', json=payload, headers=headers)

class Letterboxd:
  def __init__(self, imdb_id):
    self.base_url = 'https://api.letterboxd.com/api/v0'
    self.imdb_id = imdb_id

    self.session = requests.Session()
    self.session.params = {}

    try:
      self.api_key = config.get('Letterboxd', 'api_key')
    except (NoSectionError, NoOptionError):
      print('ERROR: %s not setup - missing api_key' % credential_file)
      sys.exit(1)

    try:
      self.api_secret = config.get('Letterboxd', 'api_secret')
    except (NoSectionError, NoOptionError):
      print('ERROR: %s not setup - missing api_secret' % credential_file)
      sys.exit(1)

  def get_access_token(self):
    try:
      return config.get('Letterboxd', 'access_token')
    except (NoSectionError, NoOptionError):
      print('ERROR: %s not setup - missing access_token' % credential_file)
      sys.exit(1)

  def get_refresh_token(self):
    try:
      return config.get('Letterboxd', 'refresh_token')
    except (NoSectionError, NoOptionError):
      print('ERROR: %s not setup - missing refresh_token' % credential_file)
      sys.exit(1)

  def get_request_params(self):
    return {
      'apikey': self.api_key,
      'nonce': uuid.uuid4(),
      'timestamp': int(time.time())
    }

  def prepare_request(self, method, url, data, params, headers):
    request = requests.Request(method.upper(), url, data=data, params=params, headers=headers)

    return self.session.prepare_request(request)

  def get_signature(self, prepared_request):
    if prepared_request.body == None:
      body = ''
    else:
      body = prepared_request.body

    signing_bytestring = b"\x00".join(
      [str.encode(prepared_request.method), str.encode(prepared_request.url), str.encode(body)]
    )

    signature = hmac.new(str.encode(self.api_secret), signing_bytestring, digestmod=sha256)
    return signature.hexdigest()

  def authenticate(self):
    method = 'post'
    url = self.base_url + '/auth/token'

    headers = {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Accept': 'application/json'
    }

    username = raw_input('Username or email address: ')
    password = getpass('Password: ')

    payload = {
      'grant_type': 'password',
      'username': username,
      'password': password
    }

    params = self.get_request_params()

    request = self.prepare_request(method, url, payload, params, headers)
    signature = self.get_signature(request)
    request.headers['Authorization'] = 'Signature ' + signature

    r = self.session.send(request)
    if r.status_code == 400:
      print('Something went wrong, you have probably used invalid credentials')
      return

    response = r.json()

    config.set('Letterboxd', 'access_token', response['access_token'])
    config.set('Letterboxd', 'refresh_token', response['refresh_token'])
    write_settings()

    print('Succesfully configured your Letterboxd sync!')

  def refresh_access_token(self):
    method = 'post'
    url = self.base_url + '/auth/token'

    headers = {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Accept': 'application/json'
    }

    payload = {
      'grant_type': 'refresh_token',
      'refresh_token': self.get_refresh_token()
    }

    params = self.get_request_params()

    request = self.prepare_request(method, url, payload, params, headers)
    signature = self.get_signature(request)
    request.headers['Authorization'] = 'Signature ' + signature

    r = self.session.send(request)
    if r.status_code == 400:
      print('Something went wrong, please authorize using `python ./trakt_letterboxd_sync.py --contentType letterboxd_authenticate --userId -1`')
      return

    response = r.json()

    config.set('Letterboxd', 'access_token', response['access_token'])
    config.set('Letterboxd', 'refresh_token', response['refresh_token'])
    write_settings()

    print('Refreshed access token succesfully!')

  def get_film_id(self):
    method = 'get'
    url = self.base_url + '/films'

    headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    }

    payload = None

    params = self.get_request_params()
    params['filmId'] = 'imdb:' + self.imdb_id

    request = self.prepare_request(method, url, payload, params, headers)
    signature = self.get_signature(request)
    request.prepare_url(request.url, {'signature': signature})

    r = self.session.send(request)

    response = r.json()
    return response['items'][0]['id']

  def log_entry(self):
    method = 'post'
    url = self.base_url + '/log-entries'

    headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    }

    payload = {
      'filmId': self.get_film_id(),
      'diaryDetails': {
        'diaryDate': datetime.datetime.today().strftime('%Y-%m-%d')
      },
      'tags': [
        'plex'
      ]
    }
    payload = json.dumps(payload)

    params = self.get_request_params()

    request = self.prepare_request(method, url, payload, params, headers)
    signature = self.get_signature(request)
    request.prepare_url(request.url, {'signature': signature})
    request.headers['Authorization'] = 'Bearer ' + self.get_access_token()

    r = self.session.send(request)

    response = r.json()
    print('Successfully logged diary entry.')

if __name__ == "__main__":
  parser = argparse.ArgumentParser(
    description="Syncing viewing activity to Trakt.tv and Letterboxd.")

  parser.add_argument('--userId', required=True, type=int,
                      help='The user_id of the current user.')

  parser.add_argument('--contentType', required=True, type=arg_decoding,
                      help='The type of content, movie or episode.')

  parser.add_argument('--tvdbId', type=int,
                      help='TVDB ID.')

  parser.add_argument('--season', type=int,
                      help='Season number.')

  parser.add_argument('--episode', type=int,
                      help='Episode number.')

  parser.add_argument('--imdbId', type=arg_decoding,
                      help='IMDB ID.')

  opts = parser.parse_args()

  if not sync_for_user(opts.userId) and not opts.userId == -1:
    print('We will not sync for this user')
    sys.exit(0)

  if opts.contentType == 'trakt_authenticate':
    trakt = Trakt(None, None)
    trakt.authenticate()
  elif opts.contentType == 'trakt_refresh':
    trakt = Trakt(None, None)
    trakt.refresh_access_token()
  elif opts.contentType == 'letterboxd_authenticate':
    letterboxd = Letterboxd(None)
    letterboxd.authenticate()
  elif opts.contentType == 'letterboxd_refresh':
    letterboxd = Letterboxd(None)
    letterboxd.refresh_access_token()
  elif opts.contentType == 'movie':
    letterboxd = Letterboxd(opts.imdbId)
    letterboxd.refresh_access_token()
    letterboxd.log_entry()
  elif opts.contentType == 'episode':
    trakt = Trakt(opts.tvdbId, opts.season, opts.episode)
    trakt.refresh_access_token()
    trakt.sync_history()
  else:
    print('ERROR: %s not found - invalid contentType' % opts.contentType)
