#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
does_not = is_not

from nti.app.products.gradebook.gradebook import GradeBookPart
from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.app.products.gradebook.grades import PersistentGrade as Grade

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.app.products.gradebook.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid


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
                              has_entries('default',  [u'Main_Title'],
                                          'no_submit', [u'Final_Grade'],
                                          'quizzes', [u'Main_Title', u'Trivial_Test'])))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_rebuild_grade_catalog(self):
        href = '/dataserver2/CourseAdmin/@@RebuildGradeCatalog'
        res = self.testapp.post(href, status=200)
        assert_that(res.json_body,
                    has_entry('Total', is_(0)))

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_remove_ghost_data(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            obj = find_object_with_ntiid(self.course_ntiid)
            book = IGradeBook(ICourseInstance(obj))
            # add fake a grade
            gbp = GradeBookPart()
            book[u'fakepart'] = gbp
            entry = GradeBookEntry()
            gbp[u'myquestion'] = entry
            entry.assignmentId = u'myquestion'
            g = Grade(username=u'ichigo', grade=85.0)
            entry[u'ichigo'] = g

        href = '/dataserver2/CourseAdmin/@@RemoveGhostCourseGradeData'
        res = self.testapp.post(href, status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(1)))
