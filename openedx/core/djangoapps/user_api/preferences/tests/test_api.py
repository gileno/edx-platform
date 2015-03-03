# -*- coding: utf-8 -*-
"""
Unit tests for preference APIs.
"""
import datetime
import ddt
import unittest
from mock import patch
from pytz import UTC

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings
from dateutil.parser import parse as parse_datetime

from student.tests.factories import UserFactory

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ...accounts.api import create_account
from ...errors import UserNotFound, UserNotAuthorized, PreferenceValidationError, PreferenceUpdateError
from ...models import UserPreference, UserProfile, UserOrgTag
from ...preferences.api import (
    get_user_preference, get_user_preferences, set_user_preference, update_user_preferences, delete_user_preference,
    update_email_opt_in
)


@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Account APIs are only supported in LMS')
class TestPreferenceAPI(TestCase):
    """
    These tests specifically cover the parts of the API methods that are not covered by test_views.py.
    This includes the specific types of error raised, and default behavior when optional arguments
    are not specified.
    """
    password = "test"

    def setUp(self):
        super(TestPreferenceAPI, self).setUp()
        self.user = UserFactory.create(password=self.password)
        self.different_user = UserFactory.create(password=self.password)
        self.staff_user = UserFactory(is_staff=True, password=self.password)
        self.no_such_user = UserFactory.create(password=self.password)
        self.no_such_user.username = "no_such_user"
        self.test_preference_key = "test_key"
        self.test_preference_value = "test_value"
        UserPreference.set_preference(self.user, self.test_preference_key, self.test_preference_value)

    def test_get_user_preference(self):
        """
        Verifies the basic behavior of get_user_preference.
        """
        self.assertEqual(
            get_user_preference(self.user, self.test_preference_key),
            self.test_preference_value
        )
        self.assertEqual(
            get_user_preference(self.staff_user, self.test_preference_key, username=self.user.username),
            self.test_preference_value
        )

    def test_get_user_preference_errors(self):
        """
        Verifies that get_user_preference returns appropriate errors.
        """
        with self.assertRaises(UserNotFound):
            get_user_preference(self.user, self.test_preference_key, username="no_such_user")

        with self.assertRaises(UserNotFound):
            get_user_preference(self.no_such_user, self.test_preference_key)

        with self.assertRaises(UserNotAuthorized):
            get_user_preference(self.different_user, self.test_preference_key, username=self.user.username)

    def test_get_user_preferences(self):
        """
        Verifies the basic behavior of get_user_preferences.
        """
        expected_user_preferences = {
            self.test_preference_key: self.test_preference_value,
        }
        self.assertEqual(get_user_preferences(self.user), expected_user_preferences)
        self.assertEqual(get_user_preferences(self.staff_user, username=self.user.username), expected_user_preferences)

    def test_get_user_preferences_errors(self):
        """
        Verifies that get_user_preferences returns appropriate errors.
        """
        with self.assertRaises(UserNotFound):
            get_user_preferences(self.user, username="no_such_user")

        with self.assertRaises(UserNotFound):
            get_user_preferences(self.no_such_user)

        with self.assertRaises(UserNotAuthorized):
            get_user_preferences(self.different_user, username=self.user.username)

    def test_set_user_preference(self):
        """
        Verifies the basic behavior of set_user_preference.
        """
        set_user_preference(self.user, self.test_preference_key, "new_value")
        self.assertEqual(
            get_user_preference(self.user, self.test_preference_key),
            "new_value"
        )

    @patch('openedx.core.djangoapps.user_api.models.UserPreference.save')
    def test_set_user_preference_errors(self, user_preference_save):
        """
        Verifies that set_user_preference returns appropriate errors.
        """
        with self.assertRaises(UserNotFound):
            set_user_preference(self.user, self.test_preference_key, "new_value", username="no_such_user")

        with self.assertRaises(UserNotFound):
            set_user_preference(self.no_such_user, self.test_preference_key, "new_value")

        with self.assertRaises(UserNotAuthorized):
            set_user_preference(self.staff_user, self.test_preference_key, "new_value", username=self.user.username)

        with self.assertRaises(UserNotAuthorized):
            set_user_preference(self.different_user, self.test_preference_key, "new_value", username=self.user.username)

        too_long_key = "x" * 256
        with self.assertRaises(PreferenceValidationError):
            set_user_preference(self.user, too_long_key, "new_value")

        user_preference_save.side_effect = [Exception, None]
        with self.assertRaises(PreferenceUpdateError):
            set_user_preference(self.user, self.test_preference_key, "new_value")

    def test_update_user_preferences(self):
        """
        Verifies the basic behavior of update_user_preferences.
        """
        expected_user_preferences = {
            self.test_preference_key: "new_value",
        }
        update_user_preferences(self.user, expected_user_preferences), expected_user_preferences
        self.assertEqual(
            get_user_preference(self.user, self.test_preference_key),
            "new_value"
        )

    @patch('openedx.core.djangoapps.user_api.models.UserPreference.delete')
    @patch('openedx.core.djangoapps.user_api.models.UserPreference.save')
    def test_update_user_preferences_errors(self, user_preference_save, user_preference_delete):
        """
        Verifies that set_user_preferences returns appropriate errors.
        """
        update_data = {
            self.test_preference_key: "new_value"
        }
        with self.assertRaises(UserNotFound):
            update_user_preferences(self.user, update_data, username="no_such_user")

        with self.assertRaises(UserNotFound):
            update_user_preferences(self.no_such_user, update_data)

        with self.assertRaises(UserNotAuthorized):
            update_user_preferences(self.staff_user, update_data, username=self.user.username)

        with self.assertRaises(UserNotAuthorized):
            update_user_preferences(self.different_user, update_data, username=self.user.username)

        too_long_key = "x" * 256
        with self.assertRaises(PreferenceValidationError):
            update_user_preferences(self.user, { too_long_key: "new_value"})

        user_preference_save.side_effect = [Exception, None]
        with self.assertRaises(PreferenceUpdateError):
            update_user_preferences(self.user, { self.test_preference_key: "new_value"})

        user_preference_delete.side_effect = [Exception, None]
        with self.assertRaises(PreferenceUpdateError):
            update_user_preferences(self.user, { self.test_preference_key: None })

    def test_delete_user_preference(self):
        """
        Verifies the basic behavior of delete_user_preference.
        """
        self.assertTrue(delete_user_preference(self.user, self.test_preference_key))
        self.assertFalse(delete_user_preference(self.user, "no_such_key"))

    @patch('openedx.core.djangoapps.user_api.models.UserPreference.delete')
    def test_delete_user_preference_errors(self, user_preference_delete):
        """
        Verifies that delete_user_preference returns appropriate errors.
        """
        with self.assertRaises(UserNotFound):
            delete_user_preference(self.user, self.test_preference_key, username="no_such_user")

        with self.assertRaises(UserNotFound):
            delete_user_preference(self.no_such_user, self.test_preference_key)

        with self.assertRaises(UserNotAuthorized):
            delete_user_preference(self.staff_user, self.test_preference_key, username=self.user.username)

        with self.assertRaises(UserNotAuthorized):
            delete_user_preference(self.different_user, self.test_preference_key, username=self.user.username)

        user_preference_delete.side_effect = [Exception, None]
        with self.assertRaises(PreferenceUpdateError):
            delete_user_preference(self.user, self.test_preference_key)


@ddt.ddt
class UpdateEmailOptInTests(ModuleStoreTestCase):

    USERNAME = u'frank-underwood'
    PASSWORD = u'ṕáśśẃőŕd'
    EMAIL = u'frank+underwood@example.com'

    def test_update_and_retrieve_preference_info(self):
        # TODO: move test into preferences API test.
        create_account(self.USERNAME, self.PASSWORD, self.EMAIL)

        user = User.objects.get(username=self.USERNAME)
        set_user_preference(user, 'preference_key', 'preference_value')

        preferences = get_user_preferences(user)
        self.assertEqual(preferences['preference_key'], 'preference_value')

    @ddt.data(
        # Check that a 27 year old can opt-in
        (27, True, u"True"),

        # Check that a 32-year old can opt-out
        (32, False, u"False"),

        # Check that someone 14 years old can opt-in
        (14, True, u"True"),

        # Check that someone 13 years old cannot opt-in (must have turned 13 before this year)
        (13, True, u"False"),

        # Check that someone 12 years old cannot opt-in
        (12, True, u"False")
    )
    @ddt.unpack
    @override_settings(EMAIL_OPTIN_MINIMUM_AGE=13)
    def test_update_email_optin(self, age, option, expected_result):
        # Create the course and account.
        course = CourseFactory.create()
        create_account(self.USERNAME, self.PASSWORD, self.EMAIL)

        # Set year of birth
        user = User.objects.get(username=self.USERNAME)
        profile = UserProfile.objects.get(user=user)
        year_of_birth = datetime.datetime.now().year - age  # pylint: disable=maybe-no-member
        profile.year_of_birth = year_of_birth
        profile.save()

        update_email_opt_in(user, course.id.org, option)
        result_obj = UserOrgTag.objects.get(user=user, org=course.id.org, key='email-optin')
        self.assertEqual(result_obj.value, expected_result)

    def test_update_email_optin_no_age_set(self):
        # Test that the API still works if no age is specified.
        # Create the course and account.
        course = CourseFactory.create()
        create_account(self.USERNAME, self.PASSWORD, self.EMAIL)

        user = User.objects.get(username=self.USERNAME)

        update_email_opt_in(user, course.id.org, True)
        result_obj = UserOrgTag.objects.get(user=user, org=course.id.org, key='email-optin')
        self.assertEqual(result_obj.value, u"True")

    @ddt.data(
        # Check that a 27 year old can opt-in, then out.
        (27, True, False, u"False"),

        # Check that a 32-year old can opt-out, then in.
        (32, False, True, u"True"),

        # Check that someone 13 years old can opt-in, then out.
        (13, True, False, u"False"),

        # Check that someone 12 years old cannot opt-in, then explicitly out.
        (12, True, False, u"False")
    )
    @ddt.unpack
    @override_settings(EMAIL_OPTIN_MINIMUM_AGE=13)
    def test_change_email_optin(self, age, option, second_option, expected_result):
        # Create the course and account.
        course = CourseFactory.create()
        create_account(self.USERNAME, self.PASSWORD, self.EMAIL)

        # Set year of birth
        user = User.objects.get(username=self.USERNAME)
        profile = UserProfile.objects.get(user=user)
        year_of_birth = datetime.datetime.now(UTC).year - age  # pylint: disable=maybe-no-member
        profile.year_of_birth = year_of_birth
        profile.save()

        update_email_opt_in(user, course.id.org, option)
        update_email_opt_in(user, course.id.org, second_option)

        result_obj = UserOrgTag.objects.get(user=user, org=course.id.org, key='email-optin')
        self.assertEqual(result_obj.value, expected_result)

    def test_update_and_retrieve_preference_info_unicode(self):
        # TODO: cover in preference API unit test.
        create_account(self.USERNAME, self.PASSWORD, self.EMAIL)
        user = User.objects.get(username=self.USERNAME)
        update_user_preferences(user, {u'ⓟⓡⓔⓕⓔⓡⓔⓝⓒⓔ_ⓚⓔⓨ': u'ǝnןɐʌ_ǝɔuǝɹǝɟǝɹd'})

        preferences = get_user_preferences(user)
        self.assertEqual(preferences[u'ⓟⓡⓔⓕⓔⓡⓔⓝⓒⓔ_ⓚⓔⓨ'], u'ǝnןɐʌ_ǝɔuǝɹǝɟǝɹd')

    def _assert_is_datetime(self, timestamp):
        if not timestamp:
            return False
        try:
            parse_datetime(timestamp)
        except ValueError:
            return False
        else:
            return True

