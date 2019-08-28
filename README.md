# Tautulli watched sync
Automatically synchronise watched TV Shows to Trakt.tv.

## Setup
Download `trakt_letterboxd_sync.py` and `sync_settings.ini.example` to your Tautulli host.
Rename `sync_settings.ini.example` to `sync_settings.ini` and add the `user_ids`, `client_id` and `client_secret`.

**Important!** Make sure `sync-settings.ini` is writable

More info below.

### Settings
`./sync-settings.ini`

```
  [Plex]
  user_ids: a comma separated list of user ids, only entries for these users will be synced
    The user id for a user can be found in your url in Tautulli when you click on a user.
  
  [Trakt]:
  Update `client_id` with the `client_id` of your registered application, see here:
    https://trakt.tv/oauth/applications > Choose your application

  To set the access code use `urn:ietf:wg:oauth:2.0:oob` as a redirect URI on your application.
  Then execute the script:
  python ./trakt_letterboxd_sync.py --contentType trakt_authenticate -userId -1
  And follow the instructions shown.

  [Letterboxd]
  Update `api_key` and `api_secret` with your Letterboxd API Key and API Shared Secret respectively.
  Look [here](https://letterboxd.com/api-beta/) as for how to receive these credentials.

  To set the access code execute the script:
  python ./trakt_letterboxd_sync.py --contentType letterboxd_authenticate --userId -1
  And follow the instructions shown.
```

### Tautulli
```
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
```
