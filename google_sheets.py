import urllib.request
import urllib.response
import urllib.parse
import time

'''
Auth json from google
{"installed":
    {
    "client_id":"1075033232306-63k2egqrvl12fv8fmeg9bsk7gr7e6ehq.apps.googleusercontent.com",
    "project_id":"gs-test-sheets-170519",
    "auth_uri":"https://accounts.google.com/o/oauth2/auth",
    "token_uri":"https://accounts.google.com/o/oauth2/token",
    "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
    "client_secret":"rNK10TfcHJ-ljP1AGFVncNDb",
    "redirect_uris":["urn:ietf:wg:oauth:2.0:oob","http://localhost"],
    }
}
'''

urlAuth = 'https://www.googleapis.com/auth/drive.readonly'
urlListFiles = 'https://www.googleapis.com/drive/v2/files '
urlSheetsReadOnly = 'https://www.googleapis.com/auth/spreadsheets.readonly'
urlSheetsReadWrite = 'https://www.googleapis.com/auth/spreadsheets'
urlGetOauthTokens = 'https://accounts.google.com/o/oauth2/auth' #re-direct the user to this link with the following POST data: https://developers.google.com/identity/protocols/OAuth2WebServer
urlRedirectUser = 'https://accounts.google.com/o/oauth2/v2/auth'

data = {'client_id': '1075033232306-63k2egqrvl12fv8fmeg9bsk7gr7e6ehq.apps.googleusercontent.com',
        #'client_secret': 'rNK10TfcHJ-ljP1AGFVncNDb',
        "project_id":"gs-test-sheets-170519",
        }

clientRedirectData = {
    'scope': 'https://www.googleapis.com/auth/spreadsheets',
    'access_type': 'offline',
    'state': 'uniqueIdentifier{}'.format(int(time.time())),
    'redirect_uri': 'http://www.millerhome.online',
    'response_type': 'code',
    'client_id': '1075033232306-63k2egqrvl12fv8fmeg9bsk7gr7e6ehq.apps.googleusercontent.com',
}
'''example clientRedirectData

    'client_id': 'Required. The client ID for your application. You can find this value in the API Console.',
    'redirect_uri': 'Required. Determines where the API server redirects the user after the user completes the authorization flow. The value must exactly match one of the redirect_uri values listed for your project in the API Console. Note that the http or https scheme, case, and trailing slash ('/') must all match. ',
    'response_type': 'Required. Determines whether the Google OAuth 2.0 endpoint returns an authorization code. Set the parameter value to code for web server applications. '
    'scope': 'Required. A space-delimited list of scopes that identify the resources that your application could access on the user\'s behalf. These values inform the consent screen that Google displays to the user.',
    'access_type': 'Recommended. Indicates whether your application can refresh access tokens when the user is not present at the browser. Valid parameter values are online, which is the default value, and offline.',
    'state': 'Recommended. Specifies any string value that your application uses to maintain state between your authorization request and the authorization server\'s response. The server returns the exact value that you send as a name=value pair in the hash (#) fragment of the redirect_uri after the user consents to or denies your application\'s access request.',
    'include_granted_scopes': 'Optional. Enables applications to use incremental authorization to request access to additional scopes in context.',
    'login_hint': 'Optional. If your application knows which user is trying to authenticate, it can use this parameter to provide a hint to the Google Authentication Server. ',
    'prompt': 'Optional. A space-delimited, case-sensitive list of prompts to present the user. If you don\'t specify this parameter, the user will be prompted only the first time your app requests access. Possible values are: ',


https://accounts.google.com/o/oauth2/v2/auth?
 scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.metadata.readonly&
 access_type=offline&
 include_granted_scopes=true&
 state=state_parameter_passthrough_value&
 redirect_uri=http%3A%2F%2Foauth2.example.com%2Fcallback&
 response_type=code&
 client_id=client_id
'''
data = urllib.parse.urlencode(clientRedirectData)

uri = urlRedirectUser + '?' + data
print('uri=', uri)
response = urllib.request.urlopen(uri)

print('response.getheaders()=', response.getheaders())
print('response=', response.read())
