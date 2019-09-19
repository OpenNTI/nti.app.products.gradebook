#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import raises
from hamcrest import calling
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
from hamcrest import same_instance
from hamcrest import greater_than_or_equal_to

from nti.testing.matchers import validly_provides

import time
import pickle
import unittest

from zope import interface

from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.app.products.gradebook.grades import Grade
from nti.app.products.gradebook.grades import GradeWeakRef
from nti.app.products.gradebook.grades import GradeContainer
from nti.app.products.gradebook.grades import PersistentGrade
from nti.app.products.gradebook.grades import PredictedGrade
from nti.app.products.gradebook.grades import PersistentMetaGrade

from nti.app.products.gradebook.gradescheme import LetterNumericGradeScheme

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import IMetaGrade
from nti.app.products.gradebook.interfaces import ISubmissionGrade

from nti.externalization.externalization import to_external_object

from nti.wref.interfaces import IWeakRef

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer


class TestGrades(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_implements(self):
        now = time.time()

        grade = PersistentGrade()
        # Username comes from parent
        container = GradeContainer()
        grade.__parent__ = container
        container.__name__ = u'foo@bar'

        assert_that(grade, validly_provides(IGrade))
        assert_that(grade, validly_provides(ISubmissionGrade))

        assert_that(grade,
                    has_property('createdTime', grade.lastModified))
        assert_that(grade,
                    has_property('lastModified', greater_than_or_equal_to(now)))

        grade.createdTime = 1
        assert_that(grade, has_property('createdTime', 1))


    def test_meta(self):
        now = time.time()

        grade = PersistentMetaGrade()
        # Username comes from parent
        container = GradeContainer()
        grade.__parent__ = container
        container.__name__ = u'foo@bar'

        assert_that(grade, validly_provides(IMetaGrade))

        assert_that(grade,
                    has_property('createdTime', grade.lastModified))
        assert_that(grade,
                    has_property('lastModified', greater_than_or_equal_to(now)))

        grade.createdTime = 1
        assert_that(grade, has_property('createdTime', 1))


    def test_unpickle_old_state(self):

        for clazz in (Grade, PersistentGrade):
            grade = clazz()
            grade.__name__ = u'foo@bar'

            state = grade.__dict__.copy()
            del state['createdTime']

            grade = Grade.__new__(Grade)
            grade.__setstate__(state)

            assert_that(grade, has_property('createdTime', grade.lastModified))

    def test_wref(self):
        assert_that(calling(GradeWeakRef).with_args(Grade()),
                    raises(TypeError))

        grade_container = _GradeContainer()
        grade = Grade()
        column = _GradeBookEntry()
        grade_container.__parent__ = column
        column[u'foo@bar'] = grade_container
        grade.__parent__ = grade_container
        grade.__name__ = 'tag:nextthought.com,2011-10:due_and_passed'

        wref = GradeWeakRef(grade)
        assert_that(wref, validly_provides(IWeakRef))

        assert_that(wref, is_(GradeWeakRef(grade)))

        d = {}
        d[wref] = 1
        assert_that(d, has_entry(GradeWeakRef(grade), 1))

        # No part in gradebook yet, cannot resolve
        assert_that(wref(), is_(none()))

        grade_container['tag:nextthought.com,2011-10:due_and_passed'] = grade
        assert_that(wref(), is_(same_instance(grade)))

        assert_that(pickle.loads(pickle.dumps(wref)), is_(wref))

    def test_externalization_predicted_grade(self):

        predicted_grade = PredictedGrade(points_earned=1, points_available=2)
        ext = to_external_object(predicted_grade)
        assert_that(ext,
                    has_entries('Correctness', is_(50),
                                'DisplayableGrade', is_(50),
                                'PointsAvailable', is_(2),
                                'PointsEarned', is_(1)))

        predicted_grade = PredictedGrade(raw_value=0.75)
        ext = to_external_object(predicted_grade)
        assert_that(ext,
                    has_entries('Correctness', is_(75),
                                'DisplayableGrade', is_(75),
                                'PointsAvailable', is_(none()),
                                'PointsEarned', is_(none())))

        predicted_grade = PredictedGrade(points_earned=1, points_available=0)
        ext = to_external_object(predicted_grade)
        # This situation doesn't make any sense,
        # so we just don't predict correctness.
        assert_that(ext,
                    has_entries('Correctness', is_(none()),
                                'DisplayableGrade', is_(none()),
                                'PointsAvailable', is_(0),
                                'PointsEarned', is_(1)))

        # By default, DisplayableGrade should be the same
        # as Correctness. However, if we're using a grading
        # scheme, then it should display a formatted value
        # according to that scheme.
        predicted_grade = PredictedGrade(raw_value=0.75)
        predicted_grade.Presentation = LetterNumericGradeScheme()
        ext = to_external_object(predicted_grade)
        assert_that(ext, has_entry('DisplayableGrade', is_('C 75')))


class _GradeBookEntry(GradeBookEntry):

    def __conform__(self, iface):
        if iface == IWeakRef:
            return _CheapWref(self)


class _GradeContainer(GradeContainer):

    def __conform__(self, iface):
        if iface == IWeakRef:
            return _CheapWref(self)


@interface.implementer(IWeakRef)
class _CheapWref(object):

    def __init__(self, gbe):
        self.gbe = gbe

    def __call__(self):
        return self.gbe

    def __eq__(self, unused_other):
        return True

    def __hash__(self):
        return 42
