#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_entries
does_not = is_not

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.externalization.oids import to_external_ntiid_oid

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.gradebook.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestAdminViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = u'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_synchronize_gradebook(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            obj = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(obj)
            ntiid = to_external_ntiid_oid(course)
        href = '/dataserver2/Objects/%s/@@SynchronizeGradebook' % ntiid
        res = self.testapp.post(href, status=200)
        assert_that(res.json_body,
                    has_entry('Items',
                              has_entries('default',  [u'Main Title'],
                                          'no_submit', [u'Final Grade'],
                                          'quizzes', [u'Main Title', u'Trivial Test'])))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_rebuild_grade_catalog(self):
        href = '/dataserver2/CourseAdmin/@@RebuildGradeCatalog'
        res = self.testapp.post(href, status=200)
        assert_that(res.json_body,
                    has_entry('Total', is_(0)))
