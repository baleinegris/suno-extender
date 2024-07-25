from SpotifyAPIConnecter import getAccessToken, getAlbum
from Authenticator import authenticatorSignup, authenticatorLogin, signInWithUID
import requests
from flask import Flask, request, redirect
from flask_cors import CORS
import urllib.parse
import time
import firebase_admin
from firebase_admin import credentials, auth, db
import Secrets

cred = credentials.Certificate(Secrets.PATH_TO_SERVICE_KEY)
firebase_admin.initialize_app(cred, {
    'databaseURL': Secrets.DATABASE_URL
})

CLIENT_ID = Secrets.CLIENT_ID
CLIENT_SECRET = Secrets.CLIENT_SECRET
TOKEN_URL = Secrets.TOKEN_URL
AUTH_URL = Secrets.AUTH_URL
REDIRECT_URI = Secrets.REDIRECT_URI
SUNO_BASE_URL = Secrets.SUNO_BASE_URL

LoggedIn = False

app = Flask(__name__)
CORS(app)
accessToken = getAccessToken()

def get_audio_information(audio_ids):
    url = f"{SUNO_BASE_URL}/api/get?ids={audio_ids}"
    response = requests.get(url)
    return response.json()

@app.route('/hello')
def hello():
    return "Hello!"

@app.route('/get-album/<string:id>')
def getDetails(id):
    return getAlbum(getAccessToken(), id)

@app.route('/login')
def login():
    scope = 'user-read-private'
    auth_query_parameters = {
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": scope,
        "client_id": CLIENT_ID
    }
    url_args = "&".join(["{}={}".format(key, urllib.parse.quote(val)) for key, val in auth_query_parameters.items()])
    auth_url = f"{AUTH_URL}/?{url_args}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    global LoggedIn
    global ACCESS_TOKEN
    global uid
    global user
    code = request.args.get('code')
    auth_token_url = TOKEN_URL
    res = requests.post(auth_token_url, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })
    res_body = res.json()
    access_token = res_body.get('access_token')
    ACCESS_TOKEN = access_token
    profile = get_user_info()
    uid = profile['id']
    user = signInWithUID(uid)
    print(user)
    return '''
    <script>
    window.opener.postMessage('loginSuccess', '*');
    window.close();
    </script>
    '''
@app.route('/test-login')
def test_login():
    print(LoggedIn)
    if LoggedIn:
        return "Logged In"
    else:
        return "Not Logged In"

@app.route('/get-user-info')
def get_user_info():
    profile = requests.get('https://api.spotify.com/v1/me', headers={
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    })
    return profile.json()

@app.route('/get-playlist-info')
def get_playlist_info():
    profile = requests.get('https://api.spotify.com/v1/me/playlists', headers={
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    })
    return profile.json()

@app.route('/extend-playlist/<string:playlist_id>')
def get_playlist_tags(playlist_id):

    def generate_audio_by_prompt(payload):
        url = f"{SUNO_BASE_URL}/api/generate"
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        return response.json()

    def get_audio_information(audio_ids):
        url = f"{SUNO_BASE_URL}/api/get?ids={audio_ids}"
        response = requests.get(url)
        return response.json()
    
    playlistinfo = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers={
        "Authorization" : f"Bearer {ACCESS_TOKEN}"
    })

    playlistinfo = playlistinfo.json()
    artists = set()
    ids = set()
    genres = set()
    for track in playlistinfo['tracks']['items']:
        artist = track['track']['artists'][0]
        artists.add(artist['name'])
        ids.add(artist['id'])
    for id in ids:
        artistinfo = requests.get(f'https://api.spotify.com/v1/artists/{id}', headers={
            "Authorization" : f"Bearer {ACCESS_TOKEN}"
        })
        artistinfo = artistinfo.json()
        for genre in artistinfo['genres']:
            genres.add(genre)
    prompt = 'A blend of: '
    for genre in genres:
        prompt += genre + ', '
    print(prompt[:200])
    data = generate_audio_by_prompt({
        "prompt": prompt[:200],
        "make_instrumental": False,
        "wait_audio": False
    })

    ids = f"{data[0]['id']},{data[1]['id']}"

    for _ in range(60):
        data = get_audio_information(ids)
        if data[0]["status"] == 'streaming':
            id1 = data[0]['id']
            url1 = data[0]['audio_url']
            id2 = data[1]['id']
            url2 = data[1]['audio_url']
            print(f"{data[0]['id']} ==> {data[0]['audio_url']}")
            print(f"{data[1]['id']} ==> {data[1]['audio_url']}")
            break
        time.sleep(5)
    
    return({
        'song1': {
            'id': id1, 
            'url':url1},
        'song2': {
            'id': id2, 
            'url': url2}
    })
@app.route('/get-audio-info/<id>')
def getAudioInfo(id):
    url = f"{SUNO_BASE_URL}/api/get?ids={id}"
    response = requests.get(url)
    return response.json()


@app.route('/sign-in/', methods=['POST'])
def signIn():
    if request.method == 'POST':
        print(request.json)
        email = request.json['email']
        password = request.json['password']
        print(email, password)
        try:
            user = authenticatorLogin(email, password)
            if user == False:
                print(user)
                return "Invalid Credentials"
            else:
                print('success')
                return {'body': {
                    "Success": True
                }}
        except Exception as e:
            return e

@app.route('/save-audio/', methods = ['POST'])
def downloadAudio():
    global uid
    if request.method == 'POST':
        try:
            id = request.json['id']
            name = request.json['name']
            print(name, id)
            url = f"{SUNO_BASE_URL}/api/get?ids={id}"
            print(url)
            data = get_audio_information(id)
            audio_url = data[0]['audio_url']
            ref = db.reference(f'Tracks/UserID/{uid}')
            print(ref.get())
            ref.push({name : audio_url})
            print(ref.get())
            return {'body': {
                "Success": True
            }}
        except Exception as e:
            return e

@app.route('/get-user-audio/')
def getUserAudio():
    global uid
    ref = db.reference(f'Tracks/UserID/{uid}')
    audios = []
    for track in ref.get():
        audio = {}
        audio['id'] = track
        trackInfo = ref.child(track).get()
        audio['name'] = list(trackInfo.keys())[0]
        audio['src'] = trackInfo[audio['name']]
        audios.append(audio)
    return audios

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)