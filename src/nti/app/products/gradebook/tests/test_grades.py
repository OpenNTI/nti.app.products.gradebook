#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import greater_than_or_equal_to

from nti.testing.matchers import validly_provides

from ..grades import Grade
from ..interfaces import IGrade

import time


def test_implements():
	now = time.time()

	grade = Grade()
	grade.__name__ = 'foo@bar'


	assert_that( grade, validly_provides(IGrade) )

	assert_that( grade, has_property( 'createdTime', grade.lastModified ))
	assert_that( grade, has_property( 'lastModified', greater_than_or_equal_to(now)))

	grade.createdTime = 1
	assert_that( grade, has_property( 'createdTime', 1 ))

def test_unpickle_old_state():

	grade = Grade()
	grade.__name__ = 'foo@bar'

	state = grade.__dict__.copy()
	del state['createdTime']

	grade = Grade.__new__(Grade)
	grade.__setstate__(state)

	assert_that( grade, has_property( 'createdTime', grade.lastModified ))
