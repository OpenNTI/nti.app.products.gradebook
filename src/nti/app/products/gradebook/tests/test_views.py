#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property

import os

from nti.dataserver.users import User

from nti.app.testing.application_webtest import SharedApplicationTestBase

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

class TestViews(ApplicationTestBase):

	@classmethod
	def _setup_library(cls, *args, **kwargs):
		lib = Library(
					paths=(os.path.join(
								   os.path.dirname(__file__),
								   'Library',
								   'CLC3403_LawAndJustice'),
				   ))
		return lib

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_fetch_all_courses(self):
		res = self.testapp.get('/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses')

		assert_that(res.json_body, has_entry('Items', has_length(2)))

		assert_that(res.json_body['Items'],
					 has_items(
						 all_of(has_entries('Duration', 'P112D',
											  'Title', 'Introduction to Water',
											  'StartDate', '2014-01-13')),
						 all_of(has_entries('Duration', None,
											  'Title', 'Law and Justice'))))
if __name__ == '__main__':
	import unittest
	unittest.main()
