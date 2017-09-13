#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that

import unittest

from nti.app.products.gradebook import gradescheme
from nti.app.products.gradebook.grades import PredictedGrade


class TestGradeScheme(unittest.TestCase):

    def test_letter_grade(self):
        lgs = gradescheme.LetterGradeScheme()

        assert_that(lgs.toLetter(100), is_('A'))
        assert_that(lgs.toLetter(91), is_('A'))
        assert_that(lgs.toLetter(90), is_('A'))
        assert_that(lgs.toLetter(68), is_('D'))
        assert_that(lgs.toLetter(51), is_('D'))
        assert_that(lgs.toLetter(20), is_('F'))

        assert_that(lgs.toNumber('A'), is_(100))
        assert_that(lgs.toNumber('B'), is_(89))
        assert_that(lgs.toNumber('C'), is_(79))
        assert_that(lgs.toNumber('D'), is_(69))
        assert_that(lgs.toNumber('F'), is_(39))

        assert_that(lgs.toCorrectness('A'), is_(1.0))
        assert_that(lgs.toCorrectness('B'), is_(0.89))
        assert_that(lgs.toCorrectness('C'), is_(0.79))
        assert_that(lgs.toCorrectness('D'), is_(0.69))
        assert_that(lgs.toCorrectness('F'), is_(0.39))

        # test with value
        assert_that(lgs.fromCorrectness(1.0), is_('A'))

        # test with grades
        grade = PredictedGrade(raw_value=0.99)
        assert_that(lgs.fromCorrectness(grade), is_('A'))

        grade = PredictedGrade(raw_value=0.85)
        assert_that(lgs.fromCorrectness(grade), is_('B'))

        grade = PredictedGrade(raw_value=0.73)
        assert_that(lgs.fromCorrectness(grade), is_('C'))

        grade = PredictedGrade(raw_value=0.65)
        assert_that(lgs.fromCorrectness(grade), is_('D'))

        grade = PredictedGrade(raw_value=0.3)
        assert_that(lgs.fromCorrectness(grade), is_('F'))

        lgs.validate('A')
        lgs.validate('B')
        with self.assertRaises(ValueError):
            lgs.validate('X')

    def test_letter_numeric_grade(self):
        lngs = gradescheme.LetterNumericGradeScheme()

        assert_that(lngs.toLetter(100), is_('A'))
        assert_that(lngs.toLetter(91), is_('A'))
        assert_that(lngs.toLetter(90), is_('A'))
        assert_that(lngs.toLetter(68), is_('D'))
        assert_that(lngs.toLetter(51), is_('D'))
        assert_that(lngs.toLetter(20), is_('F'))

        assert_that(lngs.toNumber('A'), is_(100))
        assert_that(lngs.toNumber('B'), is_(89))
        assert_that(lngs.toNumber('C'), is_(79))
        assert_that(lngs.toNumber('D'), is_(69))
        assert_that(lngs.toNumber('F'), is_(39))

        # test with value
        assert_that(lngs.fromCorrectness(1.0), is_('A'))

        # test with grades
        grade = PredictedGrade(raw_value=0.99)
        assert_that(lngs.fromCorrectness(grade), is_('A'))

        grade = PredictedGrade(raw_value=0.85)
        assert_that(lngs.fromCorrectness(grade), is_('B'))

        grade = PredictedGrade(raw_value=0.73)
        assert_that(lngs.fromCorrectness(grade), is_('C'))

        grade = PredictedGrade(raw_value=0.65)
        assert_that(lngs.fromCorrectness(grade), is_('D'))

        grade = PredictedGrade(raw_value=0.3)
        assert_that(lngs.fromCorrectness(grade), is_('F'))

        # test with value
        assert_that(lngs.toDisplayableGrade(1.0), is_('A 100'))

        grade = PredictedGrade(raw_value=0.99)
        assert_that(lngs.toDisplayableGrade(grade), is_('A 99'))

        grade = PredictedGrade(raw_value=0.85)
        assert_that(lngs.toDisplayableGrade(grade), is_('B 85'))

        grade = PredictedGrade(raw_value=0.73)
        assert_that(lngs.toDisplayableGrade(grade), is_('C 73'))

        grade = PredictedGrade(raw_value=0.65)
        assert_that(lngs.toDisplayableGrade(grade), is_('D 65'))

        grade = PredictedGrade(raw_value=0.3)
        assert_that(lngs.toDisplayableGrade(grade), is_('F 30'))

        lngs.validate('A')
        lngs.validate('B')
        with self.assertRaises(ValueError):
            lngs.validate('X')

    def test_total_points_grade_scheme(self):

        tpgs = gradescheme.TotalPointsGradeScheme()

        # We don't support raw_value for this grade scheme,
        # because it really doesn't make sense.
        grade = PredictedGrade(raw_value=0.73)
        assert_that(tpgs.toDisplayableGrade(grade), is_(None))

        grade = PredictedGrade(points_earned=30)
        assert_that(tpgs.toDisplayableGrade(grade), is_(30))

        # points_available doesn't affect our result at all
        grade = PredictedGrade(points_earned=30, points_available=100)
        assert_that(tpgs.toDisplayableGrade(grade), is_(30))

        grade = PredictedGrade(points_earned=30, points_available=10)
        assert_that(tpgs.toDisplayableGrade(grade), is_(30))

        # Only accept numeric grades
        with self.assertRaises(TypeError):
            tpgs.validate('X')

        # Negative grades are not valid
        with self.assertRaises(TypeError):
            tpgs.validate('-1')

        # Negative points earned are capped at 0.
        grade = PredictedGrade(points_earned=-30)
        assert_that(tpgs.toDisplayableGrade(grade), is_(0))

        # Grades are rounded to two decimal points
        grade = PredictedGrade(points_earned=30.178888)
        assert_that(tpgs.toDisplayableGrade(grade), is_(30.18))
