#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import raises
from hamcrest import calling
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import same_instance
from hamcrest import greater_than_or_equal_to

import time
import unittest
import cPickle as pickle

from nti.wref.interfaces import IWeakRef

from nti.app.products.gradebook.grades import Grade
from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.grades import GradeWeakRef
from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.testing.matchers import validly_provides

class TestGrades(unittest.TestCase):

	def test_implements(self):
		now = time.time()

		grade = Grade()
		grade.__name__ = 'foo@bar'


		assert_that( grade, validly_provides(IGrade) )

		assert_that( grade, has_property( 'createdTime', grade.lastModified ))
		assert_that( grade, has_property( 'lastModified', greater_than_or_equal_to(now)))

		grade.createdTime = 1
		assert_that( grade, has_property( 'createdTime', 1 ))

	def test_unpickle_old_state(self):

		grade = Grade()
		grade.__name__ = 'foo@bar'

		state = grade.__dict__.copy()
		del state['createdTime']

		grade = Grade.__new__(Grade)
		grade.__setstate__(state)

		assert_that( grade, has_property( 'createdTime', grade.lastModified ))

	def test_wref(self):

		assert_that( calling(GradeWeakRef).with_args(Grade()),
					 raises(TypeError))

		grade = Grade()
		grade.__name__ = 'foo@bar'
		column = grade.__parent__ = _GradeBookEntry()

		wref = GradeWeakRef(grade)
		assert_that( wref, validly_provides(IWeakRef) )

		assert_that( wref, is_( GradeWeakRef(grade)))

		d = {}
		d[wref] = 1
		assert_that( d, has_entry( GradeWeakRef(grade), 1 ))

		# No part in gradebook yet, cannot resolve
		assert_that( wref(), is_( none() ))

		column[grade.Username] = grade
		assert_that( wref(), is_( same_instance( grade )))

		assert_that( pickle.loads(pickle.dumps(wref)), is_(wref))

class _GradeBookEntry(GradeBookEntry):
	
	def __conform__(self, iface):
		return _CheapWref(self)
	
from zope import interface

@interface.implementer(IWeakRef)
class _CheapWref(object):
	def __init__( self, gbe ):
		self.gbe = gbe

	def __call__(self):
		return self.gbe

	def __eq__(self, other):
		return True

	def __hash__(self):
		return 42
