#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import assert_that
does_not = is_not

import unittest

from nti.app.products.gradebook.gradebook import GradeBook
from nti.app.products.gradebook.gradebook import GradeBookPart
from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IGradeBookPart
from nti.app.products.gradebook.interfaces import IGradeBookEntry

from nti.app.products.gradebook.grades import PersistentGrade as Grade

from nti.testing.matchers import verifiably_provides, validly_provides

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

class TestGradebook(unittest.TestCase):
	
	layer = SharedConfiguringTestLayer

	def test_interfaces(self):
		gb = GradeBook()
		assert_that(gb, validly_provides(IGradeBook))
		assert_that(gb, verifiably_provides(IGradeBook))

		gbp = GradeBookPart()
		gbp.order = 1
		gbp.__parent__ = gb
		gbp.__name__ = gbp.displayName = 'part'
		assert_that(gbp, validly_provides(IGradeBookPart))
		assert_that(gbp, verifiably_provides(IGradeBookPart))

		gbe = GradeBookEntry()
		gbe.order = 1
		gbe.__parent__ = gbp
		gbe.assignmentId = 'xzy'
		gbe.__name__ = gbe.displayName = 'entry'
		assert_that(gbe, validly_provides(IGradeBookEntry))
		assert_that(gbe, verifiably_provides(IGradeBookEntry))

	def test_gradebook_entry_case_insensitive_for_contains(self):
		# Because it should be case insensitive for everything,
		# but we have existing objects that aren't. Sigh.
		gbe = GradeBookEntry()
		grade = Grade()

		gbe['key'] = grade
		assert_that( 'KEY', is_in(gbe) )

		assert_that( gbe.get('KEY'), is_( grade ) )
		assert_that( gbe.__getitem__('KEY'), is_( grade ))
		
	def test_gradebook_delete(self):
		book = GradeBook()
		
		part = GradeBookPart()
		part.order = 1
		part.displayName = 'part'
		book['part'] = part
		
		entry = GradeBookEntry()
		entry.order = 1
		entry.assignmentId = 'xzy'
		entry.displayName = 'entry'
		part['entry'] = entry
		
		grade = Grade()
		entry['ichigo'] = grade
		
		assert_that(entry, has_key('ichigo'))

		book.remove_user('ichigo')
		assert_that(entry, does_not(has_key('ichigo')))
