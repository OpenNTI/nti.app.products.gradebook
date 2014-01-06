#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that

import unittest

from .. import gradescheme

class TestGradeScheme(unittest.TestCase):
	
	def test_letter_grade(self):
		lgs = gradescheme.LetterGradeScheme()

		assert_that(lgs.toLetter(100), is_('A'))
		assert_that(lgs.toLetter(91), is_('A'))
		assert_that(lgs.toLetter(90), is_('A'))
		assert_that(lgs.toLetter(68), is_('D'))
		assert_that(lgs.toLetter(51), is_('F'))

		assert_that(lgs.toNumber('A'), is_(100))
		assert_that(lgs.toNumber('B'), is_(89))
		assert_that(lgs.toNumber('C'), is_(79))
		assert_that(lgs.toNumber('D'), is_(69))
		assert_that(lgs.toNumber('F'), is_(59))

		assert_that(lgs.toCorrectness('A'), is_(1.0))
		assert_that(lgs.toCorrectness('B'), is_(0.89))
		assert_that(lgs.toCorrectness('C'), is_(0.79))
		assert_that(lgs.toCorrectness('D'), is_(0.69))
		assert_that(lgs.toCorrectness('F'), is_(0.59))

		assert_that(lgs.fromCorrectness(1.0), is_('A'))
		assert_that(lgs.fromCorrectness(0.99), is_('A'))
		assert_that(lgs.fromCorrectness(0.85), is_('B'))
		assert_that(lgs.fromCorrectness(0.73), is_('C'))
		assert_that(lgs.fromCorrectness(0.65), is_('D'))
		assert_that(lgs.fromCorrectness(0.3), is_('F'))

		lgs.validate('A')
		lgs.validate('B')
		try:
			lgs.validate('X')
			self.fail()
		except:
			pass

