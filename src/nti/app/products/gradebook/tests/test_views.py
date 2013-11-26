#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that

import os

from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library

from nti.app.testing.application_webtest import SharedApplicationTestBase

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestViews(SharedApplicationTestBase):

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

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_gradebook(self):
		res = self.testapp.get('/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses')
		links = res.json_body['Items'][0]['Links']
		href = self.courseInstanceLink(links)

		gbook = href + '/GradeBook'
		res = self.testapp.get(gbook)
		assert_that(res.json_body, has_entry('TotalPartWeight', 0.0))
		assert_that(res.json_body, has_entry('NTIID', u'tag:nextthought.com,2011-10:course-gradebook-CLC3403'))

if __name__ == '__main__':
	import unittest
	unittest.main()
