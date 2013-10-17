#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from .. import gradebook
from .. import interfaces as grades_interfaces

from .  import ConfiguringTestBase

from nti.testing.matchers import verifiably_provides, validly_provides

from hamcrest import (assert_that, has_length, has_key, has_property, is_not)

class TestGradeBook(ConfiguringTestBase):

	def test_interfaces(self):
		gb = gradebook.GradeBook()
		assert_that(gb, validly_provides(grades_interfaces.IGradeBook))
		assert_that(gb, verifiably_provides(grades_interfaces.IGradeBook))

		gbp = gradebook.GradeBookPart()
		gbp.order = 1
		gbp.__name__ = gbp.name = 'part'
		assert_that(gbp, validly_provides(grades_interfaces.IGradeBookPart))
		assert_that(gbp, verifiably_provides(grades_interfaces.IGradeBookPart))

		gbe = gradebook.GradeBookEntry()
		gbe.order = 1
		gbe.__name__ = gbe.name = 'entry'
		assert_that(gbe, validly_provides(grades_interfaces.IGradeBookEntry))
		assert_that(gbe, verifiably_provides(grades_interfaces.IGradeBookEntry))

	def test_clone(self):
		book = gradebook.GradeBook()
		part = gradebook.GradeBookPart()
		part.order = 1
		part.weight = 0.5
		part.__name__ = part.name = 'part'
		book[part.__name__] = part
		entry = gradebook.GradeBookEntry()
		entry.order = 2
		entry.weight = 0.9
		entry.questionSetID = 'xyzq'
		entry.__name__ = entry.name = 'entry'
		part[entry.__name__] = entry

		cl_book = book.clone()
		assert_that(cl_book, has_length(1))
		assert_that(cl_book, has_key('part'))
		assert_that(id(book), is_not(id(cl_book)))

		cl_part = cl_book['part']
		assert_that(id(part), is_not(id(cl_part)))
		assert_that(cl_part, has_length(1))
		assert_that(cl_part, has_property('__name__', 'part'))
		assert_that(cl_part, has_property('name', 'part'))
		assert_that(cl_part, has_property('order', 1))
		assert_that(cl_part, has_property('weight', 0.5))
		assert_that(cl_part, has_key('entry'))

		cl_entry = cl_part['entry']
		assert_that(id(entry), is_not(id(cl_entry)))
		assert_that(cl_entry, has_property('__name__', 'entry'))
		assert_that(cl_entry, has_property('name', 'entry'))
		assert_that(cl_entry, has_property('order', 2))
		assert_that(cl_entry, has_property('weight', 0.9))
		assert_that(cl_entry, has_property('questionSetID', 'xyzq'))

