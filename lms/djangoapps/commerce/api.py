import json
import logging
from simplejson import JSONDecodeError

from django.conf import settings
import jwt
import requests
from rest_framework.status import HTTP_200_OK


log = logging.getLogger(__name__)


class EommerceAPI(object):
    def __init__(self, url=None, key=None, timeout=None):
        self.url = (url or settings.ECOMMERCE_API_URL).strip('/')
        self.key = key or settings.ECOMMERCE_API_SIGNING_KEY
        self.timeout = timeout or getattr(settings, 'ECOMMERCE_API_TIMEOUT', 5)

        if not (self.url and self.key):
            raise ValueError('Values for both url and key must be set.')

    def _get_jwt(self, user):
        """
        Returns a JWT object with the specified user's info.

        Raises AttributeError if settings.ECOMMERCE_API_SIGNING_KEY is not set.
        """
        data = {
            'username': user.username,
            'email': user.email
        }
        return jwt.encode(data, self.key)

    def create_order(self, user, sku):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'JWT {}'.format(self._get_jwt(user))
        }

        url = '{}/orders/'.format(self.url)
        response = requests.post(url, data=json.dumps({'sku': sku}), headers=headers, timeout=self.timeout)

        try:
            data = response.json()
        except JSONDecodeError:
            log.error('E-Commerce API response is not valid JSON.')
            # TODO Raise API-specific error
            raise

        status_code = response.status_code

        if status_code == HTTP_200_OK:
            return data
        else:
            msg = u'Response from E-Commerce API was invalid: (%(status)d) - %(msg)s'
            msg_kwargs = {
                'status': status_code,
                'msg': data.get('user_message'),
            }
            log.error(msg, msg_kwargs)
            # TODO Raise API-specific error
