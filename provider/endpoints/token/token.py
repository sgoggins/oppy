import time
import jwt
import logging
from flask import Blueprint, request
from provider.model.authorization_request_store import authorization_requests
from provider.model.crypto import require
from provider.model import crypto


WEEK = 7 * 24 * 60 * 60

logger = logging.getLogger('token')
logger.setLevel(logging.INFO)
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

refresh_tokens = {}


class TokenRequestError(RuntimeError):
    pass


def create_blueprint(client_store, keypair):
    token_bp = Blueprint('token_bp', __name__)

    @token_bp.route('/token', methods=["POST"])
    def token():

        try:

            grant_type = require(request.form, 'grant_type', TokenRequestError('invalid_request',
                                 'grant_type parameter is missing'))
            client_id = require(request.form, 'client_id', TokenRequestError('invalid_request',
                                'client_id parameter is missing'))

            if unsupported(grant_type):
                raise TokenRequestError('invalid_request', 'grant_type not supported')

            auth_code = require(request.form, 'code', TokenRequestError('invalid_request', 'code parameter is missing'))

            auth_request = authorization_requests.get(auth_code)
            if auth_request is None:
                raise TokenRequestError('invalid_request', 'authorization request not found')

            if auth_request['client_id'] != client_id:
                raise TokenRequestError('invalid_request', 'client id mismatch')

            client = client_store.get(client_id)
            if not client:
                raise TokenRequestError('invalid_request', 'unknown client')

            token = generate_token(auth_request, keypair[0])
            logger.info(str(token))
            resp = {
                'access_token': token.decode("utf-8"),
                'token_type': 'Bearer',
                'expires_in': 3600
            }

            if not client.is_public():
                resp['refresh_token'] = create_refresh_token(client_id)

            return resp, 200
        except KeyError as ex:
            raise TokenRequestError('invalid_request', ex)
        except TokenRequestError as ex:
            logger.error(ex)
            return "Error occurred: " + ' - '.join(ex.args), 400

    def unsupported(grant_type):
        return grant_type not in ('authorization_code', )

    def generate_token(auth_request, private_key):
        now = int(time.time())
        claims = {
            'username': auth_request['username'],
            'sub': str(auth_request['id']),
            'iss': 'http://localhost:5000',
            'aud': 'urn:my_service',
            'iat': now,
            'nbf': now,
            'exp': now + 3600,
            'scope': 'read write'
        }

        token = jwt.encode(claims, private_key, algorithm='RS256')

        return token

    return token_bp


def create_refresh_token(client_id):
    now = int(time.time())
    refresh_token = crypto.generate_refresh_token()
    refresh_tokens[refresh_token] = {
        'client_id': client_id,
        'expires': now + WEEK
    }
    return refresh_token
