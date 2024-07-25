import pyrebase
from firebase_admin import auth
import Secrets

firebase = pyrebase.initialize_app(Secrets.firebaseConfig)
default_auth = firebase.auth()

def authenticatorLogin(email, password):
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        return user
    except:
        return False

def authenticatorSignup(email, password):
    try:
        user = auth.create_user_with_email_and_password(email, password)
        return user
    except:
        return False

def signInWithUID(uid):
    token = auth.create_custom_token(uid)
    decoded_token = token.decode('utf-8')
    user = default_auth.sign_in_with_custom_token(decoded_token)
    return user
