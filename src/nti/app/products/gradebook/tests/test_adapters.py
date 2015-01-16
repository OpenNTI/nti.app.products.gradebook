#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that

import unittest

from nti.contenttypes.courses.courses import CourseInstance

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

class TestAdapters(unittest.TestCase):
	
	layer = SharedConfiguringTestLayer

	@WithMockDSTrans
	def test_course_instance(self):
		ci = CourseInstance()
		gb = IGradeBook(ci, None)
		assert_that(gb, is_not(none()))
