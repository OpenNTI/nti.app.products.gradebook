#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from nti.externalization import externalization

from .. import grades
from nti.testing.base import SharedConfiguringTestBase

# import nti.dataserver.tests.mock_dataserver as mock_dataserver
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from hamcrest import assert_that
from hamcrest import none
from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry

class TestExternal(SharedConfiguringTestBase):

	set_up_packages = ('nti.dataserver', 'nti.app.products.gradebook')

	@WithMockDSTrans
	def test_grade(self):
		g = grades.Grade(entry="quiz1", grade=85.0, autograde=80.2)
		ext = externalization.to_external_object(g)
		assert_that(ext, has_entry(u'Class', 'Grade'))
		assert_that(ext, has_entry(u'grade', is_(85.0)))
		assert_that(ext, has_entry(u'entry', 'quiz1'))
		assert_that(ext, has_entry(u'autograde', is_(80.2)))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.grade'))
		assert_that(ext, has_entry(u'Last Modified', is_not(none())))
