import jwt
import logging
import requests
import sys
from jwcrypto import jwk
from urllib.parse import urlencode, quote

from flask import Flask, request, redirect, render_template
app = Flask(__name__)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)


def get_public_key(url):
    response = requests.get(url, verify=False)
    key = jwk.JWK.from_json(response.content)
    return key.export_to_pem()


public_key = get_public_key('https://localhost:5000/jwk')


@app.route("/")
def index():
    cookie = request.cookies.get('token')
    if cookie:
        logger.info('cookie: ' + cookie)
        response = requests.get('https://localhost:5002/resource', 
                                headers={'Authorization': 'Bearer ' + cookie},
                                verify=False)
        if response.status_code != 200:
            logger.warn("Response from resource server: " + response.status_code)

        return render_template('index.html', token=response.json())

    return redirect(authorize_request('https://localhost:5000/authorize', client_id='confidential_client',
                    redirect_uri='https://localhost:5001/cb', response_type='code',
                    state='96f07e0b-992a-4b5e-a61a-228bd9cfad35', scope='scope1 scope2'))


def authorize_request(url, **query_params):
    return url + '?' + urlencode(query_params)


@app.route("/cb")
def auth_code():
    code = request.args.get('code')
    logger.warning('code = ' + code)
    # get token using auth code
    access_token = get_token(code)
    logger.info(access_token)
    # store access_token as cookie
    response = redirect('/')    # redirect to index page
    response.set_cookie('token', access_token)
    return response


def get_token(auth_code):
    token_endpoint = 'https://localhost:5000/token'
    redirect_url = 'http://localhost:5001/cb'
    headers = {}
    headers['Content-Type'] = "application/x-www-form-urlencoded"
    # headers['Authorization'] = 'Basic ' + \
    #                            base64.b64encode((client_id + ':' + client_secret).encode()).decode('utf-8')

    data = {"grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": quote(redirect_url),
            "client_id": "confidential_client"}

    response = requests.post(token_endpoint, headers=headers, data=data, verify=False)
    return response.json()["access_token"]


def main():
    print('running main')
    app.run(host='0.0.0.0', port=5001, debug=app.config['TESTING'],
            ssl_context=('cert.pem', 'key.pem'))


if __name__ == "__main__":
    sys.exit(main())