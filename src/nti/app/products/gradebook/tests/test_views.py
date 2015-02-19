#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.products.gradebook.views.grading_views import is_none

from nti.app.products.gradebook.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

class TestViews(ApplicationLayerTest):
	
	layer = InstructedCourseApplicationTestLayer

	gradebook_part = {'Name':'Quizzes', 'order':1,
					  'MimeType':'application/vnd.nextthought.gradebookpart'}

	gradebook_entry = { 'Name':'Quiz1', 'order':2,
						'AssignmentId': 'tag:nextthought.com,2011-10:NextThought-gradebook-CLC3403',
						'MimeType':'application/vnd.nextthought.gradebookentry'}

	grade = {'username':'sjohnson@nextthought.com', 'grade':85, 'NTIID':None,
			 'MimeType':'application/vnd.nextthought.grade'}

	@WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
	def test_gradebook_delete(self):
		environ = self._make_extra_environ()
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'

		res = self.testapp.get('/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses', extra_environ=environ)
		href = self.require_link_href_with_rel(res.json_body['Items'][0], 'CourseInstance')

		gradebook_href = path = href + '/GradeBook'

		res = self.testapp.get(path, extra_environ=environ)
		assert_that(res.json_body, has_entry('NTIID', u'tag:nextthought.com,2011-10:NextThought-gradebook-CLC3403'))
		assert_that(res.json_body, has_entry('Items', has_length(3)))

		# As an admin, we can delete it...it will be reset on startup
		self.testapp.delete(gradebook_href, extra_environ=environ)
		res = self.testapp.get(path, extra_environ=environ)
		assert_that(res.json_body, has_entry('NTIID', u'tag:nextthought.com,2011-10:NextThought-gradebook-CLC3403'))
		assert_that( res.json_body, has_entry('Items', has_length(0)))


	def test_is_none(self):
		assert_that(is_none(None), is_(True))
		assert_that(is_none(''), is_(True))
		assert_that(is_none('-'), is_(True))
		assert_that(is_none(' - '), is_(True))
		
		assert_that(is_none(5), is_(False))
		assert_that(is_none('--'), is_(False))
		assert_that(is_none('D - '), is_(False))
		assert_that(is_none('55 D-'), is_(False))
