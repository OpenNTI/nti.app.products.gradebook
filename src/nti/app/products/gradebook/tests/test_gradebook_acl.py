#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from zope.component.hooks import getSite

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.products.gradebook.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.webtest import TestApp as _TestApp

from nti.dataserver.authorization import ROLE_SITE_ADMIN_NAME

from nti.dataserver.tests import mock_dataserver

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class TestGradebookACL(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer
    default_origin = 'https://platform.ou.edu'
    course_href = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403'
    gradebook_href = course_href + '/GradeBook'

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_regular_user_access(self):
        # Make a regular user
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            self._create_user(u'regularjoe', u'temp001', external_value={'realname': u'Regular Joe',
                                                                         'email': u'regjoe@boring.com'})
        # Regular user should 403
        regularapp = _TestApp(self.app, extra_environ=self._make_extra_environ(username=u'regularjoe'))
        regularapp.get(self.gradebook_href,
                       status=403)

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_super_user_access(self):
        adminapp = _TestApp(self.app, extra_environ=self._make_extra_environ(username=u'sjohnson@nextthought.com'))
        adminapp.get(self.gradebook_href,
                     status=200)

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_site_admin_access(self):
        # Make a site admin user
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            self._create_user(u'siteadmin', u'temp001', external_value={'realname': u'Site Admin',
                                                                         'email': u'siteadmin@test.com'})
            site = getSite()
            prm = IPrincipalRoleManager(site)
            prm.assignRoleToPrincipal(ROLE_SITE_ADMIN_NAME, u'siteadmin')

        # Site admin user should 403
        siteadminapp = _TestApp(self.app, extra_environ=self._make_extra_environ(username=u'siteadmin'))
        siteadminapp.get(self.gradebook_href,
                         status=403)
