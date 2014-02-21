#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that


import unittest

from nti.app.testing.decorators import WithSharedApplicationMockDS


from . import InstructedCourseApplicationTestLayer
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
		assert_that( res.json_body, has_entry('Items', has_length(3)))

		# As an admin, we can delete it...it will be reset on startup
		self.testapp.delete(gradebook_href, extra_environ=environ)
		res = self.testapp.get(path, extra_environ=environ)
		assert_that(res.json_body, has_entry('NTIID', u'tag:nextthought.com,2011-10:NextThought-gradebook-CLC3403'))
		assert_that( res.json_body, has_entry('Items', has_length(0)))

	@unittest.skip("WIP")
	@WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
	def test_gradebook(self):
		res = self.testapp.get('/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses')
		href = self.require_link_href_with_rel(res.json_body['Items'][0], 'CourseInstance')

		gradebook_href = path = href + '/GradeBook'
		res = self.testapp.get(path)
		#assert_that(res.json_body, has_entry('TotalPartWeight', 0.0))
		assert_that(res.json_body, has_entry('NTIID', u'tag:nextthought.com,2011-10:NextThought-gradebook-CLC3403'))

		environ = self._make_extra_environ()
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'

		data = self.gradebook_part
		res = self.testapp.post_json(path, data, extra_environ=environ)

		assert_that(res.json_body, has_entry('Class', 'GradeBookPart'))
		assert_that(res.json_body, has_entry('Creator', 'sjohnson@nextthought.com'))
		assert_that(res.json_body, has_entry('Name', 'Quizzes'))
		assert_that(res.json_body, has_entry('order', 1))
		#assert_that(res.json_body, has_entry('weight', 0.95))
		assert_that(res.json_body, has_entry('displayName', 'Quizzes'))
		assert_that(res.json_body, has_entry('MimeType', 'application/vnd.nextthought.gradebookpart'))
		assert_that(res.json_body, has_entry('NTIID', u'tag:nextthought.com,2011-10:NextThought-gradebookpart-CLC3403.Quizzes'))

		res = self.testapp.get(path)
		#assert_that(res.json_body, has_entry('TotalPartWeight', 0.95))

		part_path = path + '/Quizzes'
		res = self.testapp.get(part_path)
		assert_that(res.json_body, has_entry(u'OID', is_not(none())))
		#assert_that(res.json_body, has_entry('TotalEntryWeight', 0.0))

		data = self.gradebook_entry
		res = self.testapp.post_json(part_path, data, extra_environ=environ)

		assert_that(res.json_body, has_entry('Class', 'GradeBookEntry'))
		assert_that(res.json_body, has_entry('Creator', 'sjohnson@nextthought.com'))
		assert_that(res.json_body, has_entry('Name', 'Quiz1'))
		assert_that(res.json_body, has_entry('order', 2))
		#assert_that(res.json_body, has_entry('weight', 0.55))
		assert_that(res.json_body, has_entry('displayName', 'Quiz1'))
		assert_that(res.json_body, has_entry('MimeType', 'application/vnd.nextthought.gradebookentry'))
		assert_that(res.json_body, has_entry('NTIID', u'tag:nextthought.com,2011-10:NextThought-gradebookentry-CLC3403.Quizzes.Quiz1'))

		res = self.testapp.get(part_path)
		#assert_that(res.json_body, has_entry('TotalEntryWeight', 0.55))

		quiz_path = part_path + '/Quiz1'
		res = self.testapp.get(quiz_path)
		assert_that(res.json_body, has_entry(u'OID', is_not(none())))

		data = self.gradebook_entry.copy()
		data['Name'] = 'quizx'
		data['order'] = 3
		#data['weight'] = 0.4
		self.testapp.post_json(part_path, data, extra_environ=environ)

		res = self.testapp.get(part_path)
		#assert_that(res.json_body, has_entry('TotalEntryWeight', close_to(0.95, 0.1)))

		data = self.gradebook_entry.copy()
		data['displayName'] = '++Quiz-1++'
		res = self.testapp.put_json(quiz_path, data, extra_environ=environ)
		assert_that(res.json_body, has_entry(u'displayName', '++Quiz-1++'))

		self.testapp.delete(quiz_path, extra_environ=environ)
		res = self.testapp.get(part_path)
		#assert_that(res.json_body, has_entry('TotalEntryWeight', close_to(0.4, 0.1)))

	@unittest.skip("WIP")
	@WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
	def test_grades(self):
		res = self.testapp.get('/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses')
		href = self.require_link_href_with_rel(res.json_body['Items'][0], 'CourseInstance')

		path = href + '/GradeBook'
		part_path = path + '/Quizzes'
		environ = self._make_extra_environ()
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'

		data = self.gradebook_part
		self.testapp.post_json(path, data, extra_environ=environ)

		data = self.grade.copy()
		res = self.testapp.post_json(path, data, extra_environ=environ)
		assert_that(res.json_body, has_entry(u'grade', 85.0))
		assert_that(res.json_body, has_entry(u'NTIID', ntiid))
		assert_that(res.json_body, has_entry(u'Username', u'sjohnson@nextthought.com'))

		user_grades_path = path + '/sjohnson@nextthought.com'
		res = self.testapp.get(user_grades_path, extra_environ=environ)
		assert_that(res.json_body, has_entry(u'Items', has_length(1)))
		assert_that(res.json_body, has_entry(u'username', u'sjohnson@nextthought.com'))

		grade_path = user_grades_path + '/' + ntiid
		data['grade'] = 84
		res = self.testapp.put_json(grade_path, data, extra_environ=environ)
		assert_that(res.json_body, has_entry(u'grade', 84.0))

		self.testapp.delete(grade_path, extra_environ=environ)
		res = self.testapp.get(user_grades_path, extra_environ=environ)
		assert_that(res.json_body, has_entry(u'Items', has_length(0)))
