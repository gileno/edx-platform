import json
import httpretty

from provider.constants import PUBLIC
from provider.oauth2.models import Client
from student.tests.factories import UserFactory
from social.apps.django_app.default.models import UserSocialAuth

@httpretty.activate
class ThirdPartyOAuthTestMixin(object):
    """
    Mixin with tests for the login_oauth_token view. A TestCase that includes
    this must define the following:

    BACKEND: The name of the backend from python-social-auth
    USER_URL: The URL of the endpoint that the backend retrieves user data from
    UID_FIELD: The field in the user data that the backend uses as the user id
    """
    def setUp(self):
        super(ThirdPartyOAuthTestMixin, self).setUp()
        self.social_uid = "test_social_uid"
        self.access_token = "test_access_token"
        self.client_id = "test_client_id"
        self.oauth_client = Client.objects.create(
            client_id=self.client_id,
            client_type=PUBLIC
        )
        self.user = UserFactory()
        UserSocialAuth.objects.create(user=self.user, provider=self.BACKEND, uid=self.social_uid)

    def _setup_provider_response(self, success):
        """
        Register a mock response for the third party user information endpoint;
        success indicates whether the response status code should be 200 or 400
        """
        if success:
            status = 200
            body = json.dumps({self.UID_FIELD: self.social_uid})
        else:
            status = 400
            body = json.dumps({})
        httpretty.register_uri(
            httpretty.GET,
            self.USER_URL,
            body=body,
            status=status,
            content_type="application/json"
        )


class ThirdPartyOAuthTestMixinFacebook(object):
    """Tests access token exchange with the Facebook backend"""
    BACKEND = "facebook"
    USER_URL = "https://graph.facebook.com/me"
    # In facebook responses, the "id" field is used as the user's identifier
    UID_FIELD = "id"


class ThirdPartyOAuthTestMixinGoogle(object):
    """Tests access token exchange with the Google backend"""
    BACKEND = "google-oauth2"
    USER_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
    # In google-oauth2 responses, the "email" field is used as the user's identifier
    UID_FIELD = "email"
