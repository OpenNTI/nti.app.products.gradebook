#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that

from nti.contenttypes.courses import courses

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from .. import interfaces as grades_interfaces

from . import ConfiguringTestBase

class TestAdapters(ConfiguringTestBase):

	@WithMockDSTrans
	def test_course_instance(self):
		ci = courses.CourseInstance()
		gb = grades_interfaces.IGradeBook(ci, None)
		assert_that(gb, is_not(none()))
		grs = grades_interfaces.IGrades(ci, None)
		assert_that(grs, is_not(none()))
