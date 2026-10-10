<!-- A copy of docs/public-api.md from the Commons Radio app. Keep it in step with the API. -->

# Public API v1

The production base URL is `https://www.commonsradio.eu/api/v1`. The API returns
JSON. It only supports read operations.

## Authentication

Station routes need no authentication. Routes under `/me` accept a Better Auth
session token or a personal API key. Make personal keys on the profile page.
Send an API key in either header:

```text
Authorization: Bearer <api-key>
```

```text
x-api-key: <api-key>
```

Keys can have `catalog:read`, `library:read`, and `library:write` scopes. Station
routes check `catalog:read` when a key is present. The `/me` routes check
`library:read`. The current route list is read-only, so `library:write` is
reserved for future write routes. A missing, invalid, revoked, or expired key
returns `401 Unauthorized`. A key without the route scope returns `403
Forbidden`. Each key allows 60 requests per minute. The API returns `429 Too
Many Requests` after that limit. The API does not accept a session cookie for
`/me` routes.

## Caching

Station responses without credentials use this shared cache policy:

```text
Cache-Control: public, s-maxage=300, stale-while-revalidate=3600
```

Schedule responses use `s-maxage=60` and the same one-hour stale window. The
schedule route reads the schedule cache. It does not fetch a station schedule
from its source.

Responses under `/me`, and all requests that send credentials, use this private
policy:

```text
Cache-Control: private, no-store
```

## Examples

Search stations. Omit `q` to browse. You can also pass `country`, `city`,
`language`, `sortBy`, `limit`, and `offset`. `limit` cannot exceed 100.

```sh
curl 'https://www.commonsradio.eu/api/v1/stations?q=jazz&country=BE&limit=20&offset=0'
```

Get one station by its ID or slug:

```sh
curl 'https://www.commonsradio.eu/api/v1/stations/nts-radio'
```

Get the current and next shows from the schedule cache:

```sh
curl 'https://www.commonsradio.eu/api/v1/stations/nts-radio/schedule'
```

Get your Favorites collection:

```sh
curl -H 'Authorization: Bearer <session-token>' \
  'https://www.commonsradio.eu/api/v1/me/favorites'
```

List your collections:

```sh
curl -H 'Authorization: Bearer <session-token>' \
  'https://www.commonsradio.eu/api/v1/me/collections'
```

Get one of your collections by ID:

```sh
curl -H 'Authorization: Bearer <session-token>' \
  'https://www.commonsradio.eu/api/v1/me/collections/<collection-id>'
```

Get the OpenAPI description:

```sh
curl 'https://www.commonsradio.eu/api/v1/openapi.json'
```

## Home Assistant

Store the key in `secrets.yaml` as `commons_radio_api_key`. This REST sensor
shows the programme that is on air now on NTS Radio. Change the station slug in
`resource` for another station.

```yaml
sensor:
  - platform: rest
    name: Commons Radio on air
    resource: https://www.commonsradio.eu/api/v1/stations/nts-radio/schedule
    headers:
      x-api-key: !secret commons_radio_api_key
    value_template: >-
      {{ value_json.now.title if value_json and value_json.now else "No programme data" }}
    scan_interval: 60
```

## Node-RED

Put a Function node before an HTTP Request node. Store the key in the
`COMMONS_RADIO_API_KEY` environment variable. Use this Function node code:

```js
msg.headers = {
  "x-api-key": env.get("COMMONS_RADIO_API_KEY"),
};
return msg;
```

Set the HTTP Request node method to `GET`, the return type to a parsed JSON
object, and the URL to:

```text
https://www.commonsradio.eu/api/v1/me/favorites
```

## n8n

Create a **Header Auth** credential with the name `x-api-key` and your personal
key as the value. Add an **HTTP Request** node with these settings:

```text
Method: GET
URL: https://www.commonsradio.eu/api/v1/me/collections
Authentication: Generic Credential Type
Generic Auth Type: Header Auth
Credential: your Commons Radio Header Auth credential
```
