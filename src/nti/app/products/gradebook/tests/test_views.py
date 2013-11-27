#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import close_to
from hamcrest import has_entry
from hamcrest import assert_that

import os

from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library

from nti.app.testing.application_webtest import SharedApplicationTestBase

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestViews(SharedApplicationTestBase):

	gradebook_part = {'Name':'Quizzes', 'order':1, 'weight':0.95,
					  'MimeType':'application/vnd.nextthought.gradebookpart'}

	gradebook_entry = { 'Name':'Quiz1', 'GradeScheme':'numeric', 'order':2, 'weight':0.55,
						'MimeType':'application/vnd.nextthought.gradebookentry'}

	@classmethod
	def _setup_library(cls, *args, **kwargs):
		lib = Library(
					paths=(os.path.join(
								   os.path.dirname(__file__),
								   'Library',
								   'CLC3403_LawAndJustice'),
				   ))
		return lib

	def courseInstanceLink(self, links):
		for link in links:
			if link.get('rel', None) == u'CourseInstance':
				return link['href']
		return None

	@WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
	def test_gradebook(self):
		res = self.testapp.get('/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses')
		links = res.json_body['Items'][0]['Links']
		href = self.courseInstanceLink(links)

		path = href + '/GradeBook'
		res = self.testapp.get(path)
		assert_that(res.json_body, has_entry('TotalPartWeight', 0.0))
		assert_that(res.json_body, has_entry('NTIID', u'tag:nextthought.com,2011-10:course-gradebook-CLC3403'))

		environ = self._make_extra_environ()
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'

		data = self.gradebook_part
		res = self.testapp.post_json(path, data, extra_environ=environ)
		
		assert_that(res.json_body, has_entry('Class', 'GradeBookPart'))
		assert_that(res.json_body, has_entry('Creator', 'sjohnson@nextthought.com'))
		assert_that(res.json_body, has_entry('Name', 'Quizzes'))
		assert_that(res.json_body, has_entry('order', 1))
		assert_that(res.json_body, has_entry('weight', 0.95))
		assert_that(res.json_body, has_entry('displayName', 'Quizzes'))
		assert_that(res.json_body, has_entry('MimeType', 'application/vnd.nextthought.gradebookpart'))
		assert_that(res.json_body, has_entry('NTIID', u'tag:nextthought.com,2011-10:course-gradebookpart-CLC3403.Quizzes'))
		
		res = self.testapp.get(path)
		assert_that(res.json_body, has_entry('TotalPartWeight', 0.95))

		part_path = path + '/Quizzes'
		res = self.testapp.get(part_path)
		assert_that(res.json_body, has_entry(u'OID', is_not(none())))
		assert_that(res.json_body, has_entry('TotalEntryWeight', 0.0))

		data = self.gradebook_entry
		res = self.testapp.post_json(part_path, data, extra_environ=environ)

		assert_that(res.json_body, has_entry('Class', 'GradeBookEntry'))
		assert_that(res.json_body, has_entry('Creator', 'sjohnson@nextthought.com'))
		assert_that(res.json_body, has_entry('Name', 'Quiz1'))
		assert_that(res.json_body, has_entry('order', 2))
		assert_that(res.json_body, has_entry('weight', 0.55))
		assert_that(res.json_body, has_entry('displayName', 'Quiz1'))
		assert_that(res.json_body, has_entry('MimeType', 'application/vnd.nextthought.gradebookentry'))
		assert_that(res.json_body, has_entry('NTIID', u'tag:nextthought.com,2011-10:course-gradebookentry-CLC3403.Quizzes.Quiz1'))

		res = self.testapp.get(part_path)
		assert_that(res.json_body, has_entry('TotalEntryWeight', 0.55))

		quiz_path = part_path + '/Quiz1'
		res = self.testapp.get(quiz_path)
		assert_that(res.json_body, has_entry(u'OID', is_not(none())))

		data = self.gradebook_entry.copy()
		data['Name'] = 'quizx'
		data['order'] = 3
		data['weight'] = 0.4
		self.testapp.post_json(part_path, data, extra_environ=environ)

		res = self.testapp.get(part_path)
		assert_that(res.json_body, has_entry('TotalEntryWeight', close_to(0.95, 0.1)))

		quiz_path_del = part_path + '/quizx'
		res = self.testapp.delete(quiz_path_del)

		res = self.testapp.get(part_path)
		assert_that(res.json_body, has_entry('TotalEntryWeight', 0.55))

		data = self.gradebook_entry.copy()
		data['Name'] = 'changed'
		data['displayName'] = 'Quiz 1.x'
		res = self.testapp.put_json(quiz_path, data, extra_environ=environ)
		assert_that(res.json_body, has_entry('Name', 'Quiz1'))
		assert_that(res.json_body, has_entry('displayName', 'Quiz 1.x'))

		self.testapp.delete(part_path)
		res = self.testapp.get(path)
		assert_that(res.json_body, has_entry('TotalPartWeight', 0.0))

if __name__ == '__main__':
	import unittest
	unittest.main()
